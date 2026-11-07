"""Persistência em SQLite (biblioteca padrão)."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from financas.models import Conta, Transacao

SCHEMA = """
CREATE TABLE IF NOT EXISTS contas (
    id              TEXT PRIMARY KEY,
    item_id         TEXT NOT NULL,
    nome            TEXT NOT NULL,
    tipo            TEXT NOT NULL,
    subtipo         TEXT,
    numero          TEXT,
    saldo_centavos  INTEGER NOT NULL DEFAULT 0,
    moeda           TEXT NOT NULL DEFAULT 'BRL',
    atualizado_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transacoes (
    id                TEXT PRIMARY KEY,
    conta_id          TEXT NOT NULL REFERENCES contas(id),
    data              TEXT NOT NULL,           -- YYYY-MM-DD
    descricao         TEXT NOT NULL,
    valor_centavos    INTEGER NOT NULL,        -- sempre positivo
    tipo              TEXT NOT NULL CHECK (tipo IN ('DEBITO', 'CREDITO')),
    categoria         TEXT NOT NULL,
    categoria_banco   TEXT,
    categoria_manual  INTEGER NOT NULL DEFAULT 0,
    status            TEXT,
    moeda             TEXT NOT NULL DEFAULT 'BRL',
    criado_em         TEXT NOT NULL,
    atualizado_em     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transacoes_data ON transacoes(data);
CREATE INDEX IF NOT EXISTS idx_transacoes_categoria ON transacoes(categoria);

CREATE TABLE IF NOT EXISTS regras (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    padrao     TEXT NOT NULL UNIQUE,
    categoria  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orcamentos (
    categoria       TEXT PRIMARY KEY,
    limite_centavos INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sincronizacoes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    executada_em TEXT NOT NULL,
    desde       TEXT NOT NULL,
    ate         TEXT NOT NULL,
    novas       INTEGER NOT NULL,
    atualizadas INTEGER NOT NULL
);
"""


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Banco:
    def __init__(self, caminho: str = "financas.db"):
        self.conn = sqlite3.connect(caminho)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def fechar(self) -> None:
        self.conn.close()

    # ---------------------------------------------------------------- contas
    def salvar_conta(self, c: Conta) -> None:
        self.conn.execute(
            """INSERT INTO contas (id, item_id, nome, tipo, subtipo, numero, saldo_centavos,
                                   moeda, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 nome=excluded.nome, tipo=excluded.tipo, subtipo=excluded.subtipo,
                 numero=excluded.numero, saldo_centavos=excluded.saldo_centavos,
                 moeda=excluded.moeda, atualizado_em=excluded.atualizado_em""",
            (c.id, c.item_id, c.nome, c.tipo, c.subtipo, c.numero, c.saldo_centavos,
             c.moeda, _agora()),
        )
        self.conn.commit()

    def listar_contas(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM contas ORDER BY nome").fetchall()

    # ------------------------------------------------------------ transações
    def salvar_transacao(self, t: Transacao, categoria: str) -> str:
        """Insere ou atualiza. Retorna 'nova', 'atualizada' ou 'igual'."""
        atual = self.conn.execute("SELECT * FROM transacoes WHERE id = ?", (t.id,)).fetchone()
        agora = _agora()
        if atual is None:
            self.conn.execute(
                """INSERT INTO transacoes (id, conta_id, data, descricao, valor_centavos, tipo,
                       categoria, categoria_banco, status, moeda, criado_em, atualizado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (t.id, t.conta_id, t.data.isoformat(), t.descricao, t.valor_centavos, t.tipo,
                 categoria, t.categoria_banco, t.status, t.moeda, agora, agora),
            )
            return "nova"
        nova_categoria = atual["categoria"] if atual["categoria_manual"] else categoria
        campos = (t.data.isoformat(), t.descricao, t.valor_centavos, t.tipo, nova_categoria,
                  t.categoria_banco, t.status, t.moeda)
        antigos = (atual["data"], atual["descricao"], atual["valor_centavos"], atual["tipo"],
                   atual["categoria"], atual["categoria_banco"], atual["status"], atual["moeda"])
        if campos == antigos:
            return "igual"
        self.conn.execute(
            """UPDATE transacoes SET data=?, descricao=?, valor_centavos=?, tipo=?, categoria=?,
                   categoria_banco=?, status=?, moeda=?, atualizado_em=? WHERE id=?""",
            (*campos, agora, t.id),
        )
        return "atualizada"

    def commit(self) -> None:
        self.conn.commit()

    def buscar_transacoes(self, inicio: date | None = None, fim: date | None = None,
                          categoria: str | None = None, tipo: str | None = None,
                          texto: str | None = None, limite: int | None = None) -> list[sqlite3.Row]:
        sql = ["SELECT t.*, c.nome AS conta_nome FROM transacoes t "
               "JOIN contas c ON c.id = t.conta_id WHERE 1=1"]
        params: list = []
        if inicio:
            sql.append("AND t.data >= ?"); params.append(inicio.isoformat())
        if fim:
            sql.append("AND t.data <= ?"); params.append(fim.isoformat())
        if categoria:
            sql.append("AND t.categoria = ? COLLATE NOCASE"); params.append(categoria)
        if tipo:
            sql.append("AND t.tipo = ?"); params.append(tipo)
        if texto:
            sql.append("AND t.descricao LIKE ?"); params.append(f"%{texto}%")
        sql.append("ORDER BY t.data DESC, t.id")
        if limite:
            sql.append("LIMIT ?"); params.append(limite)
        return self.conn.execute(" ".join(sql), params).fetchall()

    def definir_categoria_manual(self, transacao_id: str, categoria: str) -> bool:
        cur = self.conn.execute(
            "UPDATE transacoes SET categoria=?, categoria_manual=1, atualizado_em=? WHERE id=?",
            (categoria, _agora(), transacao_id))
        self.conn.commit()
        return cur.rowcount > 0

    def transacoes_automaticas(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT id, descricao, categoria, categoria_banco FROM transacoes "
            "WHERE categoria_manual = 0").fetchall()

    def atualizar_categoria(self, transacao_id: str, categoria: str) -> None:
        self.conn.execute("UPDATE transacoes SET categoria=?, atualizado_em=? WHERE id=?",
                          (categoria, _agora(), transacao_id))

    # ---------------------------------------------------------------- regras
    def adicionar_regra(self, padrao: str, categoria: str) -> None:
        self.conn.execute(
            "INSERT INTO regras (padrao, categoria) VALUES (?, ?) "
            "ON CONFLICT(padrao) DO UPDATE SET categoria=excluded.categoria",
            (padrao, categoria))
        self.conn.commit()

    def remover_regra(self, regra_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM regras WHERE id = ?", (regra_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def listar_regras(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM regras ORDER BY id").fetchall()

    def regras_como_tuplas(self) -> list[tuple[str, str]]:
        return [(r["padrao"], r["categoria"]) for r in self.listar_regras()]

    # ------------------------------------------------------------ orçamentos
    def definir_orcamento(self, categoria: str, limite_centavos: int) -> None:
        self.conn.execute(
            "INSERT INTO orcamentos (categoria, limite_centavos) VALUES (?, ?) "
            "ON CONFLICT(categoria) DO UPDATE SET limite_centavos=excluded.limite_centavos",
            (categoria, limite_centavos))
        self.conn.commit()

    def listar_orcamentos(self) -> dict[str, int]:
        rows = self.conn.execute("SELECT * FROM orcamentos").fetchall()
        return {r["categoria"]: r["limite_centavos"] for r in rows}

    # -------------------------------------------------------- sincronizações
    def registrar_sincronizacao(self, desde: date, ate: date, novas: int, atualizadas: int) -> None:
        self.conn.execute(
            "INSERT INTO sincronizacoes (executada_em, desde, ate, novas, atualizadas) "
            "VALUES (?, ?, ?, ?, ?)",
            (_agora(), desde.isoformat(), ate.isoformat(), novas, atualizadas))
        self.conn.commit()

    def ultima_sincronizacao(self) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM sincronizacoes ORDER BY id DESC LIMIT 1").fetchone()
