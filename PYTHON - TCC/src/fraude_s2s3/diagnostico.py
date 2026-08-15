"""Registro de pendências metodológicas ("pontos de correção").

Requisito do orientando: *"caso tenha algo que esteja fora do alcance ou
métrica faltando, pedir uma correção ao final de todo código e apontar a área
designada"*.

Implementação: qualquer módulo do pipeline pode registrar uma pendência com
:func:`registrar`. Ao final do notebook, :func:`relatorio` imprime a lista
consolidada, ordenada por severidade, com a área responsável e a ação pedida.
Nada é silenciado: se um indicador não pôde ser construído, isso vira texto
no relatório em vez de virar ``NaN`` invisível dentro do modelo.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum


class Severidade(IntEnum):
    """Impacto da pendência sobre a validade do resultado."""

    BLOQUEIA = 3      # resultado não pode ser reportado enquanto não resolvido
    COMPROMETE = 2    # resultado pode ser reportado, mas com ressalva explícita
    OBSERVA = 1       # registro de transparência; não invalida nada


ROTULO = {
    Severidade.BLOQUEIA: "BLOQUEIA RESULTADO",
    Severidade.COMPROMETE: "COMPROMETE INTERPRETACAO",
    Severidade.OBSERVA: "OBSERVACAO",
}


@dataclass
class Pendencia:
    area: str            # módulo/etapa onde a pendência nasce
    item: str            # o que está faltando ou incerto
    impacto: str         # o que deixa de ser possível afirmar
    acao: str            # o que precisa ser feito, por quem
    severidade: Severidade = Severidade.COMPROMETE
    registrado_em: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


_PENDENCIAS: list[Pendencia] = []


def registrar(area: str, item: str, impacto: str, acao: str,
              severidade: Severidade = Severidade.COMPROMETE) -> Pendencia:
    """Registra uma pendência. Idempotente por (area, item)."""
    for p in _PENDENCIAS:
        if p.area == area and p.item == item:
            return p
    p = Pendencia(area=area, item=item, impacto=impacto, acao=acao, severidade=severidade)
    _PENDENCIAS.append(p)
    return p


def limpar() -> None:
    _PENDENCIAS.clear()


def pendencias() -> list[Pendencia]:
    return sorted(_PENDENCIAS, key=lambda p: (-int(p.severidade), p.area, p.item))


def ha_bloqueio() -> bool:
    return any(p.severidade == Severidade.BLOQUEIA for p in _PENDENCIAS)


def relatorio(largura: int = 96) -> str:
    """Texto consolidado das pendências, para o fim do notebook."""
    itens = pendencias()
    linhas: list[str] = []
    reg = "=" * largura
    linhas.append(reg)
    linhas.append("PONTOS DE CORRECAO — pendencias levantadas pela execucao do pipeline".center(largura))
    linhas.append(reg)

    if not itens:
        linhas.append("")
        linhas.append("Nenhuma pendencia registrada nesta execucao.")
        linhas.append("Atencao: ausencia de pendencia nao equivale a validacao metodologica —")
        linhas.append("significa apenas que nenhuma verificacao automatizada falhou.")
        linhas.append(reg)
        return "\n".join(linhas)

    contagem = {s: sum(1 for p in itens if p.severidade == s) for s in Severidade}
    linhas.append("")
    linhas.append(
        f"  {contagem[Severidade.BLOQUEIA]} bloqueio(s) | "
        f"{contagem[Severidade.COMPROMETE]} ressalva(s) | "
        f"{contagem[Severidade.OBSERVA]} observacao(oes)"
    )
    linhas.append("")

    for i, p in enumerate(itens, 1):
        linhas.append("-" * largura)
        linhas.append(f"[{i:02d}] {ROTULO[p.severidade]}   ::   AREA: {p.area}")
        linhas.append("-" * largura)
        for titulo, corpo in (("Item", p.item), ("Impacto", p.impacto), ("Correcao pedida", p.acao)):
            embrulho = textwrap.wrap(corpo, width=largura - 20) or [""]
            linhas.append(f"  {titulo + ':':<18}{embrulho[0]}")
            for extra in embrulho[1:]:
                linhas.append(f"  {'':<18}{extra}")
        linhas.append("")

    linhas.append(reg)
    if ha_bloqueio():
        linhas.append("EXISTE PENDENCIA BLOQUEANTE. Os escores produzidos nesta execucao NAO devem")
        linhas.append("ser reportados como resultado no TCC ate que o item seja resolvido.")
        linhas.append(reg)
    return "\n".join(linhas)


def para_dataframe():
    """Versão tabular das pendências (para anexo do TCC)."""
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "severidade": ROTULO[p.severidade],
                "area": p.area,
                "item": p.item,
                "impacto": p.impacto,
                "correcao_pedida": p.acao,
                "registrado_em": p.registrado_em,
            }
            for p in pendencias()
        ]
    )
