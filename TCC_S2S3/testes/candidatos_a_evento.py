"""Lista instituições que merecem busca nas fontes públicas.

Procurar as 72 instituições do painel no Diário Oficial é inviável. Este script
usa o próprio painel para produzir uma lista curta de candidatos, por dois
critérios observáveis:

1. **Saída do painel** — a instituição deixa de aparecer antes do fim do
   recorte. Pode ser liquidação, mas também fusão, incorporação ou mudança de
   segmento. Não é rótulo; é motivo para procurar.

2. **Sinalização episódica concentrada** — a instituição é sinalizada por vários
   testes analíticos em trimestres próximos. Também não é rótulo; é motivo para
   procurar.

A saída é um CSV com as instituições a pesquisar, na ordem em que vale a pena
pesquisá-las, com o trimestre a partir do qual procurar.

Uso:

    python testes\\candidatos_a_evento.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

TRATADOS = RAIZ / "dados" / "tratados"
LARGURA = 74


def main() -> int:
    import pandas as pd

    from fraude_s2s3 import testes_analiticos

    caminho = TRATADOS / "painel_indicadores_S2S3.csv"
    if not caminho.exists():
        print(f"\n  Painel nao encontrado em {caminho}")
        print("  Rode antes: python processar_base.py")
        return 2

    ind = pd.read_csv(caminho)
    ultimo = int(ind["anomes"].max())

    print("=" * LARGURA)
    print("  CANDIDATOS A BUSCA NAS FONTES PUBLICAS".center(LARGURA))
    print("=" * LARGURA)
    print(f"\n  Painel: {len(ind):,} observacoes, {ind['cod_inst'].nunique()} "
          f"instituicoes, ate {ultimo}")

    nomes = (ind.groupby("cod_inst")["Instituição"].last()
             if "Instituição" in ind.columns else None)

    # -- 1. saida do painel ------------------------------------------------
    ultimo_por_inst = ind.groupby("cod_inst")["anomes"].max()
    saiu = ultimo_por_inst[ultimo_por_inst < ultimo]

    print("\n" + "-" * LARGURA)
    print("1. INSTITUICOES QUE SAEM DO PAINEL")
    print("-" * LARGURA)
    if saiu.empty:
        print("\n  Nenhuma. Todas as instituicoes vao ate o fim do recorte.")
    else:
        print(f"\n  {len(saiu)} instituicao(oes). Procure no DOU a partir do")
        print("  trimestre seguinte ao ultimo em que aparecem.\n")
        for cod, fim in saiu.sort_values().items():
            nome = nomes.get(cod, "") if nomes is not None else ""
            print(f"    {str(cod):<12} ultimo trimestre {fim}   {nome[:44]}")
        print("\n  LEMBRE: sair do painel nao significa liquidacao. Fusao,")
        print("  incorporacao e mudanca de segmento produzem o mesmo efeito,")
        print("  e sao mais comuns. Confirme na fonte antes de registrar.")

    # -- 2. sinalizacao episodica concentrada ------------------------------
    print("\n" + "-" * LARGURA)
    print("2. SINALIZACAO EPISODICA CONCENTRADA")
    print("-" * LARGURA)
    try:
        sinal = testes_analiticos.aplicar(ind, registrar_diagnostico=False)
        foco = testes_analiticos.foco_de_exame(sinal)
    except Exception as e:
        print(f"\n  Nao foi possivel aplicar os testes: {e}")
        foco = None

    linhas = []
    if foco is not None and len(foco):
        pico = (foco.groupby(["cod_inst", "anomes"])["n_testes_sinalizados"]
                .max().reset_index())
        melhor = (pico.sort_values("n_testes_sinalizados", ascending=False)
                  .drop_duplicates("cod_inst").head(15))
        print(f"\n  Instituicoes com mais testes simultaneos, e o trimestre do")
        print("  pico — e dele que vale partir na busca.\n")
        for r in melhor.itertuples():
            nome = nomes.get(r.cod_inst, "") if nomes is not None else ""
            print(f"    {str(r.cod_inst):<12} {r.anomes}  "
                  f"{r.n_testes_sinalizados} testes   {nome[:40]}")
            linhas.append({
                "cod_inst": r.cod_inst,
                "Instituição": nome,
                "motivo": "sinalizacao_concentrada",
                "anomes_referencia": r.anomes,
                "detalhe": f"{r.n_testes_sinalizados} testes simultaneos",
            })
        print("\n  LEMBRE: sinalizacao e divergencia frente aos pares, nao")
        print("  indicio de irregularidade. Serve para ordenar a busca.")

    for cod, fim in saiu.items():
        linhas.append({
            "cod_inst": cod,
            "Instituição": nomes.get(cod, "") if nomes is not None else "",
            "motivo": "saida_do_painel",
            "anomes_referencia": int(fim),
            "detalhe": "ultimo trimestre em que aparece",
        })

    if linhas:
        saida = TRATADOS / "candidatos_a_evento.csv"
        pd.DataFrame(linhas).to_csv(saida, index=False, encoding="utf-8-sig")
        print("\n" + "=" * LARGURA)
        print(f"  Gravado: {saida.relative_to(RAIZ)}")
        print("=" * LARGURA)

    print("\n  COMO USAR\n")
    print("    Para cada instituicao desta lista, procure o nome no Diario")
    print("    Oficial da Uniao, a partir do trimestre de referencia, pelos")
    print("    termos: liquidacao extrajudicial, RAET, intervencao,")
    print("    cancelamento da autorizacao para funcionamento.")
    print("\n    Achando o ato, registre em dados/externos/eventos_publicos.csv")
    print("    com a data do ATO e a URL do documento.")
    print("\n    Nao achando nada, isso tambem e resultado: registre que a")
    print("    busca foi feita e nada foi encontrado.")
    print("\n    Ver docs/FONTES_COMPLEMENTARES.md, secoes 1.1 a 1.11.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
