"""Relatórios e exportação."""

from __future__ import annotations

import calendar
import csv
from dataclasses import dataclass, field
from datetime import date

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

    @property
    def saldo(self) -> int:
        return self.receitas - self.gastos


def resumo_mensal(banco: Banco, mes: str) -> ResumoMensal:
    inicio, fim = intervalo_mes(mes)
    resumo = ResumoMensal(mes=mes)
    for t in banco.buscar_transacoes(inicio=inicio, fim=fim):
        if t["tipo"] == CREDITO:
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
