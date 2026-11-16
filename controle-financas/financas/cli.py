"""Interface de linha de comando.  Uso: python -m financas <comando> --help"""

from __future__ import annotations

import argparse
import uuid
from datetime import date

from financas.config import carregar_config
from financas.db import Banco
from financas.models import DEBITO, TIPOS_INVESTIMENTO, Investimento, formatar_brl, para_centavos
from financas.provedores import criar_provedor
from financas.relatorios import (carteira, exportar_csv, intervalo_mes, mes_atual, patrimonio,
                                 resumo_mensal)
from financas.sync import recategorizar, sincronizar


def _data(txt: str) -> date:
    return date.fromisoformat(txt)


def cmd_sincronizar(args, banco, config):
    if args.fake:
        config = type(config)(**{**config.__dict__, "provedor": "fake"})
    provedor = criar_provedor(config)
    r = sincronizar(banco, provedor, desde=args.desde, dias_iniciais=config.dias_iniciais)
    print(f"Sincronizado de {r.desde} até {r.ate}: {r.contas} conta(s), "
          f"{r.novas} transação(ões) nova(s), {r.atualizadas} atualizada(s), "
          f"{r.investimentos} investimento(s).")
    if r.investimentos_resgatados:
        print(f"{r.investimentos_resgatados} investimento(s) não aparecem mais no banco "
              "(resgatados) e foram marcados como inativos.")


def cmd_contas(args, banco, config):
    for c in banco.listar_contas():
        print(f"{c['nome']:<30} {c['tipo']:<8} {c['numero'] or '':<12} "
              f"{formatar_brl(c['saldo_centavos']):>16}  ({c['id']})")


def cmd_gastos(args, banco, config):
    inicio, fim = intervalo_mes(args.mes) if args.mes else (None, None)
    tipo = None if args.todos else DEBITO
    linhas = banco.buscar_transacoes(inicio=inicio, fim=fim, categoria=args.categoria,
                                     tipo=tipo, texto=args.busca, limite=args.limite)
    total = 0
    for t in linhas:
        sinal = -1 if t["tipo"] == DEBITO else 1
        total += sinal * t["valor_centavos"]
        print(f"{t['data']}  {formatar_brl(sinal * t['valor_centavos']):>14}  "
              f"{t['categoria']:<16} {t['descricao'][:40]:<40} [{t['id']}]")
    print(f"\n{len(linhas)} transação(ões) | total: {formatar_brl(total)}")


def cmd_resumo(args, banco, config):
    mes = args.mes or mes_atual()
    r = resumo_mensal(banco, mes)
    orcamentos = banco.listar_orcamentos()
    print(f"=== Resumo {mes} ===")
    print(f"Receitas: {formatar_brl(r.receitas):>16}")
    print(f"Gastos:   {formatar_brl(r.gastos):>16}  ({r.quantidade_gastos} lançamentos)")
    print(f"Saldo:    {formatar_brl(r.saldo):>16}\n")
    print("Gastos por categoria:")
    for cat, valor in r.por_categoria.items():
        pct = valor / r.gastos * 100 if r.gastos else 0
        linha = f"  {cat:<18} {formatar_brl(valor):>14}  {pct:5.1f}%"
        if cat in orcamentos:
            limite = orcamentos[cat]
            uso = valor / limite * 100 if limite else 0
            alerta = "  ⚠ ESTOUROU" if valor > limite else ""
            linha += f"   orçamento {formatar_brl(limite)} ({uso:.0f}%){alerta}"
        print(linha)
    if r.fora_do_total:
        print("\nFora do total (só mudam o dinheiro de lugar):")
        for cat, (entradas, saidas) in sorted(r.fora_do_total.items()):
            print(f"  {cat:<22} entrou {formatar_brl(entradas):>13}   "
                  f"saiu {formatar_brl(saidas):>13}")


def cmd_categorizar(args, banco, config):
    if banco.definir_categoria_manual(args.id, args.categoria):
        print(f"Transação {args.id} -> {args.categoria}")
    else:
        print(f"Transação {args.id} não encontrada.")
        return 1


def cmd_regra(args, banco, config):
    if args.acao == "adicionar":
        banco.adicionar_regra(args.padrao, args.categoria)
        n = recategorizar(banco)
        print(f"Regra salva: '{args.padrao}' -> {args.categoria} ({n} transação(ões) recategorizada(s))")
    elif args.acao == "remover":
        ok = banco.remover_regra(args.regra_id)
        print("Regra removida." if ok else "Regra não encontrada.")
    else:
        for r in banco.listar_regras():
            print(f"[{r['id']}] '{r['padrao']}' -> {r['categoria']}")


def cmd_orcamento(args, banco, config):
    if args.acao == "definir":
        banco.definir_orcamento(args.categoria, para_centavos(args.valor))
        print(f"Orçamento de {args.categoria}: {formatar_brl(para_centavos(args.valor))}/mês")
    else:
        for cat, lim in sorted(banco.listar_orcamentos().items()):
            print(f"{cat:<18} {formatar_brl(lim):>14}")


def cmd_recategorizar(args, banco, config):
    print(f"{recategorizar(banco)} transação(ões) recategorizada(s).")


def cmd_exportar(args, banco, config):
    inicio, fim = intervalo_mes(args.mes) if args.mes else (None, None)
    n = exportar_csv(banco, args.arquivo, inicio, fim)
    print(f"{n} transação(ões) exportada(s) para {args.arquivo}")


def _pct(rend: int | None, base: int) -> str:
    if rend is None or not base:
        return "      -"
    return f"{rend / base * 100:+6.2f}%"


def cmd_investimentos(args, banco, config):
    c = carteira(banco)
    if not c.grupos:
        print("Nenhum investimento. Rode 'sincronizar' ou use 'investimento adicionar'.")
        return
    for g in c.grupos.values():
        pct_carteira = g.saldo / c.total * 100 if c.total else 0
        print(f"\n## {g.tipo}: {formatar_brl(g.saldo)} ({pct_carteira:.1f}% da carteira)")
        for inv in g.itens:
            rend = (inv["saldo_centavos"] - inv["valor_aplicado_centavos"]
                    if inv["valor_aplicado_centavos"] is not None else None)
            extra = " | ".join(x for x in [
                inv["taxa"], f"vence {inv['vencimento']}" if inv["vencimento"] else "",
                "manual" if inv["item_id"] == "manual" else ""] if x)
            print(f"  {inv['nome'][:34]:<34} {formatar_brl(inv['saldo_centavos']):>15}  "
                  f"rend. {_pct(rend, inv['valor_aplicado_centavos'] or 0)}  {extra}  [{inv['id']}]")
    print(f"\nTOTAL INVESTIDO: {formatar_brl(c.total)}")
    if c.rendimento is not None:
        print(f"Rendimento (onde o valor aplicado é conhecido): {formatar_brl(c.rendimento)} "
              f"({_pct(c.rendimento, c.aplicado).strip()})")


def cmd_investimento(args, banco, config):
    if args.acao == "adicionar":
        inv = Investimento(
            id=f"manual-{uuid.uuid4().hex[:8]}", item_id="manual", nome=args.nome,
            tipo=args.tipo, subtipo=args.subtipo or "", codigo=args.codigo or "",
            saldo_centavos=para_centavos(args.saldo),
            valor_aplicado_centavos=para_centavos(args.aplicado) if args.aplicado else None,
            quantidade=args.quantidade, vencimento=args.vencimento, taxa=args.taxa or "",
            instituicao=args.instituicao or "")
        banco.salvar_investimento(inv)
        print(f"Investimento cadastrado: {inv.nome} ({inv.id})")
    elif args.acao == "atualizar":
        atual = banco.buscar_investimento(args.id)
        if atual is None or atual["item_id"] != "manual":
            print("Investimento manual não encontrado (os do Open Finance se atualizam sozinhos).")
            return 1
        inv = Investimento(
            id=atual["id"], item_id="manual", nome=atual["nome"], tipo=atual["tipo"],
            subtipo=atual["subtipo"] or "", codigo=atual["codigo"] or "",
            saldo_centavos=para_centavos(args.saldo),
            valor_aplicado_centavos=(para_centavos(args.aplicado) if args.aplicado
                                     else atual["valor_aplicado_centavos"]),
            quantidade=atual["quantidade"],
            vencimento=date.fromisoformat(atual["vencimento"]) if atual["vencimento"] else None,
            taxa=atual["taxa"] or "", instituicao=atual["instituicao"] or "")
        banco.salvar_investimento(inv)
        print(f"{inv.nome}: saldo atualizado para {formatar_brl(inv.saldo_centavos)}")
    elif args.acao == "remover":
        ok = banco.remover_investimento_manual(args.id)
        print("Removido." if ok else "Só é possível remover investimentos manuais.")


def cmd_patrimonio(args, banco, config):
    p = patrimonio(banco)
    print("=== Patrimônio ===")
    print(f"Contas:          {formatar_brl(p.contas):>16}")
    print(f"Investimentos:   {formatar_brl(p.investimentos):>16}")
    print(f"Faturas cartão:  {formatar_brl(-p.cartoes):>16}")
    print(f"PATRIMÔNIO LÍQ.: {formatar_brl(p.liquido):>16}")
    evolucao = banco.evolucao_investimentos()
    if len(evolucao) > 1:
        print("\nEvolução dos investimentos (fim de cada mês):")
        anterior = None
        for e in evolucao:
            var = f"  ({formatar_brl(e['total_centavos'] - anterior)})" if anterior is not None else ""
            print(f"  {e['mes']}  {formatar_brl(e['total_centavos']):>16}{var}")
            anterior = e["total_centavos"]


def cmd_diagnostico(args, banco, config):
    """Confere a configuração e a conexão com a Pluggy sem gravar nada."""
    print(f"Provedor configurado: {config.provedor}")
    print(f"Banco de dados:       {config.db_path}")
    if config.provedor != "pluggy":
        print("-> Para usar o Open Finance real, coloque FINANCAS_PROVEDOR=pluggy no .env")
        return
    print(f"Client ID preenchido: {'sim' if config.pluggy_client_id else 'NÃO'}")
    print(f"Client Secret:        {'preenchido' if config.pluggy_client_secret else 'NÃO preenchido'}")
    print(f"Items configurados:   {len(config.pluggy_item_ids)}")
    import requests

    from financas.pluggy_client import PluggyClient, PluggyError

    try:
        cliente = PluggyClient(config.pluggy_client_id, config.pluggy_client_secret,
                               config.pluggy_item_ids)
        cliente._autenticar()
        print("Autenticação na Pluggy: OK")
        problemas = 0
        for item_id in config.pluggy_item_ids:
            try:
                item = cliente._get(f"/items/{item_id}")
            except PluggyError as e:
                problemas += 1
                if "(404)" in str(e):
                    print(f"  item {item_id}: NÃO ENCONTRADO na sua aplicação.")
                    print("     -> Este ID não pertence ao seu Client ID (ex.: ID copiado do"
                          " meu.pluggy.ai).")
                    print("        Conecte pelo dashboard (conector MeuPluggy) e use o Item ID"
                          " que aparecer lá.")
                else:
                    print(f"  item {item_id}: ERRO {e}")
                continue
            conector = (item.get("connector") or {}).get("name") or "?"
            cliente.item_ids = [item_id]
            contas = cliente.listar_contas()
            invs = cliente.listar_investimentos()
            print(f"  item {item_id} [{conector}, status {item.get('status')}]: "
                  f"{len(contas)} conta(s), {len(invs)} investimento(s)")
            for c in contas:
                print(f"     - {c.nome} ({c.tipo})")
            if not contas and not invs:
                problemas += 1
                print("     -> Nenhum dado ainda. Se o status for UPDATING, aguarde e rode de novo.")
    except (PluggyError, requests.RequestException) as e:
        print(f"ERRO: {e}")
        return 1
    if problemas:
        print(f"Atenção: {problemas} item(s) com problema. Corrija antes de sincronizar.")
        return 1
    print("Tudo certo! Agora rode: python -m financas sincronizar")


def montar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="financas", description="Controle de finanças via Open Finance")
    sub = p.add_subparsers(dest="comando", required=True)

    sub.add_parser("diagnostico", help="Testa a configuração e a conexão com a Pluggy") \
        .set_defaults(func=cmd_diagnostico)

    s = sub.add_parser("sincronizar", help="Baixa transações do Open Finance")
    s.add_argument("--desde", type=_data, help="Data inicial (AAAA-MM-DD)")
    s.add_argument("--fake", action="store_true", help="Usa dados fictícios")
    s.set_defaults(func=cmd_sincronizar)

    sub.add_parser("contas", help="Lista contas e saldos").set_defaults(func=cmd_contas)

    s = sub.add_parser("gastos", help="Lista gastos")
    s.add_argument("--mes", help="AAAA-MM")
    s.add_argument("--categoria")
    s.add_argument("--busca", help="Texto na descrição")
    s.add_argument("--limite", type=int, default=50)
    s.add_argument("--todos", action="store_true", help="Inclui receitas")
    s.set_defaults(func=cmd_gastos)

    s = sub.add_parser("resumo", help="Resumo mensal por categoria")
    s.add_argument("--mes", help="AAAA-MM (padrão: mês atual)")
    s.set_defaults(func=cmd_resumo)

    s = sub.add_parser("categorizar", help="Define a categoria de uma transação manualmente")
    s.add_argument("id"); s.add_argument("categoria")
    s.set_defaults(func=cmd_categorizar)

    s = sub.add_parser("regra", help="Regras automáticas de categorização")
    rs = s.add_subparsers(dest="acao", required=True)
    a = rs.add_parser("adicionar"); a.add_argument("padrao"); a.add_argument("categoria")
    r = rs.add_parser("remover"); r.add_argument("regra_id", type=int)
    rs.add_parser("listar")
    s.set_defaults(func=cmd_regra)

    s = sub.add_parser("orcamento", help="Limites mensais por categoria")
    os_ = s.add_subparsers(dest="acao", required=True)
    d = os_.add_parser("definir"); d.add_argument("categoria"); d.add_argument("valor")
    os_.add_parser("listar")
    s.set_defaults(func=cmd_orcamento)

    sub.add_parser("recategorizar", help="Reaplica as regras").set_defaults(func=cmd_recategorizar)

    sub.add_parser("investimentos", help="Carteira de investimentos por tipo") \
        .set_defaults(func=cmd_investimentos)

    s = sub.add_parser("investimento", help="Cadastra investimentos que não vêm do Open Finance")
    ins = s.add_subparsers(dest="acao", required=True)
    a = ins.add_parser("adicionar")
    a.add_argument("nome")
    a.add_argument("--tipo", required=True, choices=sorted(TIPOS_INVESTIMENTO))
    a.add_argument("--saldo", required=True, help="Valor atual, ex.: 1500.50")
    a.add_argument("--aplicado", help="Quanto você aplicou (para calcular rendimento)")
    a.add_argument("--subtipo", help="CDB, LCI, TREASURY, STOCK, CRYPTO...")
    a.add_argument("--codigo", help="Ticker, ex.: PETR4")
    a.add_argument("--quantidade", type=float)
    a.add_argument("--vencimento", type=_data, help="AAAA-MM-DD")
    a.add_argument("--taxa", help='ex.: "110%% CDI"')
    a.add_argument("--instituicao")
    u = ins.add_parser("atualizar"); u.add_argument("id")
    u.add_argument("--saldo", required=True); u.add_argument("--aplicado")
    r = ins.add_parser("remover"); r.add_argument("id")
    s.set_defaults(func=cmd_investimento)

    sub.add_parser("patrimonio", help="Contas + investimentos - cartões") \
        .set_defaults(func=cmd_patrimonio)

    s = sub.add_parser("exportar", help="Exporta transações para CSV")
    s.add_argument("arquivo"); s.add_argument("--mes", help="AAAA-MM")
    s.set_defaults(func=cmd_exportar)
    return p


def main(argv: list[str] | None = None) -> int:
    args = montar_parser().parse_args(argv)
    config = carregar_config()
    banco = Banco(config.db_path)
    try:
        return args.func(args, banco, config) or 0
    finally:
        banco.fechar()
