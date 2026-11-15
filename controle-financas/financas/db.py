"""Persistência em SQLite (biblioteca padrão)."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from financas.models import Conta, Investimento, Transacao

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

CREATE TABLE IF NOT EXISTS investimentos (
    id                      TEXT PRIMARY KEY,
    item_id                 TEXT NOT NULL,          -- 'manual' se cadastrado à mão
    nome                    TEXT NOT NULL,
    tipo                    TEXT NOT NULL,
    subtipo                 TEXT,
    codigo                  TEXT,
    saldo_centavos          INTEGER NOT NULL,       -- valor líquido atual
    valor_bruto_centavos    INTEGER,
    valor_aplicado_centavos INTEGER,
    quantidade              REAL,
    vencimento              TEXT,
    taxa                    TEXT,
    instituicao             TEXT,
    moeda                   TEXT NOT NULL DEFAULT 'BRL',
    ativo                   INTEGER NOT NULL DEFAULT 1,  -- 0 = resgatado/sumiu do banco
    atualizado_em           TEXT NOT NULL
);

-- Uma "foto" por investimento por dia, para ver a evolução do patrimônio
CREATE TABLE IF NOT EXISTS investimentos_historico (
    investimento_id TEXT NOT NULL REFERENCES investimentos(id) ON DELETE CASCADE,
    data            TEXT NOT NULL,
    saldo_centavos  INTEGER NOT NULL,
    PRIMARY KEY (investimento_id, data)
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

    # --------------------------------------------------------- investimentos
    def salvar_investimento(self, i: Investimento, data_foto: date | None = None) -> str:
        """Insere/atualiza a posição e grava a foto do dia. Retorna 'novo' ou 'atualizado'."""
        existe = self.conn.execute("SELECT 1 FROM investimentos WHERE id = ?",
                                   (i.id,)).fetchone()
        self.conn.execute(
            """INSERT INTO investimentos (id, item_id, nome, tipo, subtipo, codigo, saldo_centavos,
                   valor_bruto_centavos, valor_aplicado_centavos, quantidade, vencimento, taxa,
                   instituicao, moeda, ativo, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
               ON CONFLICT(id) DO UPDATE SET
                 nome=excluded.nome, tipo=excluded.tipo, subtipo=excluded.subtipo,
                 codigo=excluded.codigo, saldo_centavos=excluded.saldo_centavos,
                 valor_bruto_centavos=excluded.valor_bruto_centavos,
                 valor_aplicado_centavos=COALESCE(excluded.valor_aplicado_centavos,
                                                  investimentos.valor_aplicado_centavos),
                 quantidade=excluded.quantidade, vencimento=excluded.vencimento,
                 taxa=excluded.taxa, instituicao=excluded.instituicao, moeda=excluded.moeda,
                 ativo=1, atualizado_em=excluded.atualizado_em""",
            (i.id, i.item_id, i.nome, i.tipo, i.subtipo, i.codigo, i.saldo_centavos,
             i.valor_bruto_centavos, i.valor_aplicado_centavos, i.quantidade,
             i.vencimento.isoformat() if i.vencimento else None, i.taxa, i.instituicao,
             i.moeda, _agora()),
        )
        self.conn.execute(
            "INSERT INTO investimentos_historico (investimento_id, data, saldo_centavos) "
            "VALUES (?, ?, ?) ON CONFLICT(investimento_id, data) "
            "DO UPDATE SET saldo_centavos=excluded.saldo_centavos",
            (i.id, (data_foto or date.today()).isoformat(), i.saldo_centavos))
        self.conn.commit()
        return "atualizado" if existe else "novo"

    def desativar_investimentos_ausentes(self, item_ids: set[str], ids_vistos: set[str]) -> int:
        """Marca como inativos (resgatados) os investimentos desses items que não vieram mais."""
        alterados = 0
        for item_id in item_ids:
            rows = self.conn.execute(
                "SELECT id FROM investimentos WHERE item_id = ? AND ativo = 1",
                (item_id,)).fetchall()
            for r in rows:
                if r["id"] not in ids_vistos:
                    self.conn.execute("UPDATE investimentos SET ativo=0, atualizado_em=? "
                                      "WHERE id=?", (_agora(), r["id"]))
                    alterados += 1
        self.conn.commit()
        return alterados

    def listar_investimentos(self, incluir_inativos: bool = False) -> list[sqlite3.Row]:
        sql = "SELECT * FROM investimentos"
        if not incluir_inativos:
            sql += " WHERE ativo = 1"
        return self.conn.execute(sql + " ORDER BY tipo, saldo_centavos DESC").fetchall()

    def remover_investimento_manual(self, investimento_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM investimentos WHERE id = ? AND item_id = 'manual'",
                                (investimento_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def buscar_investimento(self, investimento_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM investimentos WHERE id = ?",
                                 (investimento_id,)).fetchone()

    def evolucao_investimentos(self) -> list[sqlite3.Row]:
        """Total investido no último registro de cada mês (AAAA-MM, total_centavos)."""
        return self.conn.execute(
            """WITH ultimo AS (
                   SELECT investimento_id, substr(data, 1, 7) AS mes, MAX(data) AS data
                   FROM investimentos_historico GROUP BY investimento_id, mes)
               SELECT u.mes, SUM(h.saldo_centavos) AS total_centavos
               FROM ultimo u JOIN investimentos_historico h
                 ON h.investimento_id = u.investimento_id AND h.data = u.data
               GROUP BY u.mes ORDER BY u.mes""").fetchall()

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
