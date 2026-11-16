"""Monta os dados de cada tela do app a partir do banco local.

Sem nada de interface aqui: só dicionários/listas prontos para exibir.
Assim dá para testar tudo com pytest, sem celular.
"""

from __future__ import annotations

from datetime import date

from financas.db import Banco
from financas.models import CREDITO, DEBITO, formatar_brl
from financas.relatorios import carteira, intervalo_mes, patrimonio, resumo_mensal
from financas.sync import recategorizar, sincronizar

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def ultimos_meses(hoje: date, quantidade: int = 12) -> list[str]:
    """['2026-11', '2026-10', ...] começando pelo mês de `hoje`."""
    ano, mes = hoje.year, hoje.month
    meses = []
    for _ in range(quantidade):
        meses.append(f"{ano:04d}-{mes:02d}")
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
    return meses


def rotulo_mes(mes: str) -> str:
    """'2026-11' -> 'nov/2026'"""
    ano, m = mes.split("-")
    return f"{MESES[int(m) - 1]}/{ano}"


def data_curta(iso: str) -> str:
    """'2026-10-15' -> '15/10'"""
    return f"{iso[8:10]}/{iso[5:7]}" if iso and len(iso) >= 10 else iso or ""


def _pct(parte: int, total: int) -> float:
    return parte / total * 100 if total else 0.0


# ------------------------------------------------------------------- telas
def tela_resumo(banco: Banco, mes: str) -> dict:
    r = resumo_mensal(banco, mes)
    orcamentos = banco.listar_orcamentos()
    categorias = []
    for nome, valor in r.por_categoria.items():
        limite = orcamentos.get(nome)
        categorias.append({
            "nome": nome,
            "valor": formatar_brl(valor),
            "pct": _pct(valor, r.gastos),
            "orcamento": formatar_brl(limite) if limite else "",
            "uso_orcamento": _pct(valor, limite) if limite else 0.0,
            "estourou": bool(limite) and valor > limite,
        })
    return {
        "mes": mes,
        "rotulo": rotulo_mes(mes),
        "sem_dados": not banco.listar_contas(),
        "receitas": formatar_brl(r.receitas),
        "gastos": formatar_brl(r.gastos),
        "saldo": formatar_brl(r.saldo),
        "saldo_positivo": r.saldo >= 0,
        "quantidade": r.quantidade_gastos,
        "categorias": categorias,
        "fora_do_total": [
            {"nome": nome, "entrou": formatar_brl(e), "saiu": formatar_brl(s)}
            for nome, (e, s) in sorted(r.fora_do_total.items())
        ],
    }


def tela_gastos(banco: Banco, mes: str, categoria: str | None = None,
                limite: int = 300) -> dict:
    inicio, fim = intervalo_mes(mes)
    todas = banco.buscar_transacoes(inicio=inicio, fim=fim)
    categorias = sorted({t["categoria"] for t in todas})
    linhas = [t for t in todas if not categoria or t["categoria"] == categoria]
    total = sum((-1 if t["tipo"] == DEBITO else 1) * t["valor_centavos"] for t in linhas)
    itens = []
    for t in linhas[:limite]:
        sinal = -1 if t["tipo"] == DEBITO else 1
        itens.append({
            "id": t["id"],
            "data": data_curta(t["data"]),
            "descricao": t["descricao"] or "(sem descrição)",
            "valor": formatar_brl(sinal * t["valor_centavos"]),
            "entrada": t["tipo"] == CREDITO,
            "categoria": t["categoria"],
            "conta": t["conta_nome"],
        })
    return {
        "categorias": categorias,
        "itens": itens,
        "quantidade": len(linhas),
        "cortado": len(linhas) > limite,
        "total": formatar_brl(total),
    }


def tela_investimentos(banco: Banco) -> dict:
    c = carteira(banco)
    grupos = []
    for g in c.grupos.values():
        itens = []
        for inv in g.itens:
            aplicado = inv["valor_aplicado_centavos"]
            rend = None
            if aplicado:
                rend = f"{(inv['saldo_centavos'] - aplicado) / aplicado * 100:+.2f}%"
            detalhes = [x for x in [
                f"rend. {rend}" if rend else "",
                inv["taxa"] or "",
                f"vence {data_curta(inv['vencimento'])}/{inv['vencimento'][:4]}"
                if inv["vencimento"] else "",
                "manual" if inv["item_id"] == "manual" else "",
            ] if x]
            itens.append({
                "nome": inv["nome"],
                "valor": formatar_brl(inv["saldo_centavos"]),
                "detalhes": " · ".join(detalhes),
            })
        grupos.append({
            "nome": g.tipo,
            "total": formatar_brl(g.saldo),
            "pct": _pct(g.saldo, c.total),
            "itens": itens,
        })
    rendimento = None
    if c.rendimento is not None:
        rendimento = (f"{formatar_brl(c.rendimento)} "
                      f"({c.rendimento / c.aplicado * 100:+.2f}%)" if c.aplicado else "")
    return {"total": formatar_brl(c.total), "rendimento": rendimento, "grupos": grupos}


def tela_patrimonio(banco: Banco) -> dict:
    p = patrimonio(banco)
    contas = [{
        "nome": c["nome"],
        "tipo": "Cartão" if c["tipo"] == "CREDIT" else "Conta",
        "saldo": formatar_brl(-abs(c["saldo_centavos"]) if c["tipo"] == "CREDIT"
                              else c["saldo_centavos"]),
    } for c in banco.listar_contas()]
    evolucao = []
    anterior = None
    for e in banco.evolucao_investimentos():
        variacao = (formatar_brl(e["total_centavos"] - anterior)
                    if anterior is not None else "")
        evolucao.append({"mes": rotulo_mes(e["mes"]),
                         "total": formatar_brl(e["total_centavos"]),
                         "variacao": variacao})
        anterior = e["total_centavos"]
    ultima = banco.ultima_sincronizacao()
    return {
        "contas": formatar_brl(p.contas),
        "investimentos": formatar_brl(p.investimentos),
        "faturas": formatar_brl(-p.cartoes),
        "liquido": formatar_brl(p.liquido),
        "liquido_positivo": p.liquido >= 0,
        "lista_contas": contas,
        "evolucao": evolucao,
        "ultima_sync": (ultima["executada_em"].replace("T", " ")[:16] if ultima else ""),
    }


# ------------------------------------------------------------ ações
def listar_regras(banco: Banco) -> list[dict]:
    return [{"id": r["id"], "padrao": r["padrao"], "categoria": r["categoria"]}
            for r in banco.listar_regras()]


def adicionar_regra(banco: Banco, padrao: str, categoria: str) -> int:
    """Salva a regra e reaplica em tudo; devolve quantas transações mudaram."""
    padrao, categoria = (padrao or "").strip(), (categoria or "").strip()
    if not padrao or not categoria:
        raise ValueError("Preencha o texto e a categoria.")
    banco.adicionar_regra(padrao, categoria)
    return recategorizar(banco)


def remover_regra(banco: Banco, regra_id: int) -> int:
    banco.remover_regra(regra_id)
    return recategorizar(banco)


def sincronizar_pluggy(db_path: str, client_id: str, client_secret: str,
                       item_ids: list[str], dias_iniciais: int = 365,
                       provedor=None) -> str:
    """Roda numa thread separada: abre a própria conexão SQLite e fecha no fim.

    `provedor` só é usado nos testes (FakeProvider); no app vem a Pluggy.
    """
    if provedor is None:
        from financas.pluggy_client import PluggyClient
        provedor = PluggyClient(client_id, client_secret, item_ids)
    banco = Banco(db_path)
    try:
        r = sincronizar(banco, provedor, dias_iniciais=dias_iniciais)
    finally:
        banco.fechar()
    return (f"Sincronizado: {r.contas} conta(s), {r.novas} lançamento(s) novo(s), "
            f"{r.atualizadas} atualizado(s), {r.investimentos} investimento(s).")
