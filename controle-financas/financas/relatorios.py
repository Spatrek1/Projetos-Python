"""Relatórios e exportação."""

from __future__ import annotations

import calendar
import csv
from dataclasses import dataclass, field
from datetime import date

from financas.categorias import CATEGORIAS_FORA_DO_TOTAL
from financas.db import Banco
from financas.models import CREDITO, DEBITO


def intervalo_mes(mes: str) -> tuple[date, date]:
    """'2026-11' -> (2026-11-01, 2026-11-30)"""
    ano, m = (int(p) for p in mes.split("-"))
    return date(ano, m, 1), date(ano, m, calendar.monthrange(ano, m)[1])


def mes_atual() -> str:
    return date.today().strftime("%Y-%m")


@dataclass
class ResumoMensal:
    mes: str
    receitas: int = 0
    gastos: int = 0
    por_categoria: dict[str, int] = field(default_factory=dict)
    quantidade_gastos: int = 0
    # categoria -> [entradas, saídas] das movimentações que não são gasto/receita
    fora_do_total: dict[str, list[int]] = field(default_factory=dict)

    @property
    def saldo(self) -> int:
        return self.receitas - self.gastos


def resumo_mensal(banco: Banco, mes: str) -> ResumoMensal:
    inicio, fim = intervalo_mes(mes)
    resumo = ResumoMensal(mes=mes)
    for t in banco.buscar_transacoes(inicio=inicio, fim=fim):
        if t["categoria"] in CATEGORIAS_FORA_DO_TOTAL:
            par = resumo.fora_do_total.setdefault(t["categoria"], [0, 0])
            par[0 if t["tipo"] == CREDITO else 1] += t["valor_centavos"]
        elif t["tipo"] == CREDITO:
            resumo.receitas += t["valor_centavos"]
        elif t["tipo"] == DEBITO:
            resumo.gastos += t["valor_centavos"]
            resumo.quantidade_gastos += 1
            resumo.por_categoria[t["categoria"]] = (
                resumo.por_categoria.get(t["categoria"], 0) + t["valor_centavos"])
    resumo.por_categoria = dict(sorted(resumo.por_categoria.items(), key=lambda kv: -kv[1]))
    return resumo


def exportar_csv(banco: Banco, caminho: str, inicio: date | None = None,
                 fim: date | None = None) -> int:
    linhas = banco.buscar_transacoes(inicio=inicio, fim=fim)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["data", "conta", "descricao", "tipo", "valor", "categoria", "id"])
        for t in linhas:
            valor = f"{t['valor_centavos'] / 100:.2f}".replace(".", ",")
            w.writerow([t["data"], t["conta_nome"], t["descricao"], t["tipo"], valor,
                        t["categoria"], t["id"]])
    return len(linhas)


@dataclass
class GrupoInvestimento:
    tipo: str
    saldo: int = 0
    aplicado: int = 0          # soma só dos que têm valor aplicado conhecido
    saldo_com_aplicado: int = 0
    itens: list = field(default_factory=list)

    @property
    def rendimento(self) -> int | None:
        return self.saldo_com_aplicado - self.aplicado if self.aplicado else None


@dataclass
class Carteira:
    grupos: dict[str, GrupoInvestimento] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(g.saldo for g in self.grupos.values())

    @property
    def aplicado(self) -> int:
        return sum(g.aplicado for g in self.grupos.values())

    @property
    def rendimento(self) -> int | None:
        base = sum(g.saldo_com_aplicado for g in self.grupos.values())
        return base - self.aplicado if self.aplicado else None


def carteira(banco: Banco) -> Carteira:
    from financas.models import nome_grupo_investimento

    c = Carteira()
    for inv in banco.listar_investimentos():
        nome = nome_grupo_investimento(inv["tipo"], inv["subtipo"])
        g = c.grupos.setdefault(nome, GrupoInvestimento(tipo=nome))
        g.saldo += inv["saldo_centavos"]
        if inv["valor_aplicado_centavos"] is not None:
            g.aplicado += inv["valor_aplicado_centavos"]
            g.saldo_com_aplicado += inv["saldo_centavos"]
        g.itens.append(inv)
    c.grupos = dict(sorted(c.grupos.items(), key=lambda kv: -kv[1].saldo))
    return c


@dataclass
class Patrimonio:
    contas: int = 0       # saldo em contas correntes/poupança
    cartoes: int = 0      # fatura atual dos cartões (dívida, positivo)
    investimentos: int = 0

    @property
    def liquido(self) -> int:
        return self.contas + self.investimentos - self.cartoes


def patrimonio(banco: Banco) -> Patrimonio:
    p = Patrimonio()
    for conta in banco.listar_contas():
        if conta["tipo"] == "CREDIT":
            p.cartoes += abs(conta["saldo_centavos"])
        else:
            p.contas += conta["saldo_centavos"]
    p.investimentos = carteira(banco).total
    return p
