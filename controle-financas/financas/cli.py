"""Interface de linha de comando.  Uso: python -m financas <comando> --help"""

from __future__ import annotations

import argparse
from datetime import date

from financas.config import carregar_config
from financas.db import Banco
from financas.models import DEBITO, formatar_brl, para_centavos
from financas.provedores import criar_provedor
from financas.relatorios import exportar_csv, intervalo_mes, mes_atual, resumo_mensal
from financas.sync import recategorizar, sincronizar


def _data(txt: str) -> date:
    return date.fromisoformat(txt)


def cmd_sincronizar(args, banco, config):
    if args.fake:
        config = type(config)(**{**config.__dict__, "provedor": "fake"})
    provedor = criar_provedor(config)
    r = sincronizar(banco, provedor, desde=args.desde, dias_iniciais=config.dias_iniciais)
    print(f"Sincronizado de {r.desde} até {r.ate}: {r.contas} conta(s), "
          f"{r.novas} transação(ões) nova(s), {r.atualizadas} atualizada(s).")


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


def montar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="financas", description="Controle de finanças via Open Finance")
    sub = p.add_subparsers(dest="comando", required=True)

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
