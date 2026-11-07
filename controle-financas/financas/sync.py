"""Sincronização: baixa contas e transações do provedor e grava no banco local."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from financas.categorias import categorizar
from financas.db import Banco
from financas.provedores import Provedor

# Transações recentes podem mudar (pendente -> lançada), então sempre
# reprocessamos alguns dias antes da última sincronização.
JANELA_REPROCESSAMENTO = 7


@dataclass
class ResultadoSync:
    desde: date
    ate: date
    contas: int = 0
    novas: int = 0
    atualizadas: int = 0


def calcular_inicio(banco: Banco, hoje: date, dias_iniciais: int) -> date:
    ultima = banco.ultima_sincronizacao()
    if ultima is None:
        return hoje - timedelta(days=dias_iniciais)
    return date.fromisoformat(ultima["ate"]) - timedelta(days=JANELA_REPROCESSAMENTO)


def sincronizar(banco: Banco, provedor: Provedor, desde: date | None = None,
                ate: date | None = None, dias_iniciais: int = 365) -> ResultadoSync:
    ate = ate or date.today()
    desde = desde or calcular_inicio(banco, ate, dias_iniciais)
    resultado = ResultadoSync(desde=desde, ate=ate)
    regras = banco.regras_como_tuplas()

    for conta in provedor.listar_contas():
        banco.salvar_conta(conta)
        resultado.contas += 1
        for t in provedor.listar_transacoes(conta.id, desde, ate):
            categoria = categorizar(t.descricao, t.categoria_banco, regras)
            status = banco.salvar_transacao(t, categoria)
            if status == "nova":
                resultado.novas += 1
            elif status == "atualizada":
                resultado.atualizadas += 1
        banco.commit()

    banco.registrar_sincronizacao(desde, ate, resultado.novas, resultado.atualizadas)
    return resultado


def recategorizar(banco: Banco) -> int:
    """Reaplica regras em transações não categorizadas manualmente."""
    regras = banco.regras_como_tuplas()
    alteradas = 0
    for row in banco.transacoes_automaticas():
        nova = categorizar(row["descricao"], row["categoria_banco"] or "", regras)
        if nova != row["categoria"]:
            banco.atualizar_categoria(row["id"], nova)
            alteradas += 1
    banco.commit()
    return alteradas
