"""Confere se o painel tratado basta para rodar o estudo sem a base bruta.

A base bruta do IF.data serve para **produzir** o painel de indicadores. Uma
vez produzido, ele é autossuficiente para a partição temporal, a rede, os
baselines, os seis testes analíticos e a interpretação.

Este script diz, a partir do que existe em dados/tratados/, exatamente quais
seções do notebook rodam e quais ficam bloqueadas — sem supor nada.

Uso:

    python testes\\conferir_painel_tratado.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

TRATADOS = RAIZ / "dados" / "tratados"
LARGURA = 74

#: Colunas sem as quais a modelagem não se sustenta.
ESSENCIAIS = ("cod_inst", "anomes", "segmento")

#: O que cada etapa exige para rodar.
ETAPAS = (
    ("7  Painel e partição temporal", "painel_indicadores_S2S3.csv", ()),
    ("8  Auditoria de vazamento", "painel_indicadores_S2S3.csv", ()),
    ("9  Autoencoder", "painel_indicadores_S2S3.csv", ()),
    ("10 Rede sequencial (GRU)", "painel_indicadores_S2S3.csv", ()),
    ("11 Comparação com métodos simples", "painel_indicadores_S2S3.csv", ()),
    ("12 Interpretação", "painel_indicadores_S2S3.csv", ()),
    ("13 Lei de Newcomb-Benford", "painel_conceitos_S2S3.csv", ()),
    ("13.2 Os seis testes analíticos", "painel_indicadores_S2S3.csv",
     ("cobertura_provisao", "peso_carteira", "sgi_bancario", "aqi_bancario",
      "levi_bancario", "nim", "accrual_bancario")),
    ("15 XGBoost e LightGBM", "painel_indicadores_S2S3.csv", ()),
)


def main() -> int:
    import pandas as pd

    print("=" * LARGURA)
    print("  O QUE DA PARA RODAR COM O QUE VOCE TEM".center(LARGURA))
    print("=" * LARGURA)
    print(f"\n  Pasta: {TRATADOS}")

    if not TRATADOS.exists():
        print("\n  A pasta dados\\tratados nao existe.")
        print("\n  Se voce tem o painel em outra pasta (dentro de TESTES-ANALITICOS,")
        print("  por exemplo), mova painel_indicadores_S2S3.csv para ca.")
        return 2

    quadros: dict[str, pd.DataFrame] = {}
    print("\n  Arquivos encontrados:\n")
    for arq in sorted(TRATADOS.glob("*.csv")):
        try:
            df = pd.read_csv(arq)
            quadros[arq.name] = df
            print(f"    {arq.name:<42} {len(df):>6,} linhas  {df.shape[1]:>3} colunas")
        except Exception as e:
            print(f"    {arq.name:<42} ILEGIVEL: {e}")

    if not quadros:
        print("    (nenhum)")
        return 2

    ind = quadros.get("painel_indicadores_S2S3.csv")
    if ind is not None:
        print("\n  Painel de indicadores:")
        faltam = [c for c in ESSENCIAIS if c not in ind.columns]
        if faltam:
            print(f"    FALTAM colunas essenciais: {faltam}")
        else:
            print(f"    Instituicoes : {ind['cod_inst'].nunique()}")
            print(f"    Trimestres   : {ind['anomes'].nunique()} "
                  f"({ind['anomes'].min()} a {ind['anomes'].max()})")
            por_seg = ind.groupby('segmento')['cod_inst'].nunique()
            print(f"    Segmentos    : " + ", ".join(f"{s} ({n})" for s, n in por_seg.items()))
            if "peso_carteira" in ind.columns:
                print("    peso_carteira: presente (condicao de escopo de T1 e T2)")
            else:
                print("    peso_carteira: AUSENTE — painel anterior a essa correcao.")
                print("                   T1 e T2 rodam, mas sem o corte de materialidade,")
                print("                   e voltam a sinalizar bancos de atacado.")

    print("\n" + "-" * LARGURA)
    print("  SECOES DO NOTEBOOK")
    print("-" * LARGURA + "\n")

    rodam, bloqueadas = 0, []
    for nome, exige_arq, exige_cols in ETAPAS:
        df = quadros.get(exige_arq)
        if df is None:
            print(f"    [ nao ]  {nome}")
            print(f"             falta {exige_arq}")
            bloqueadas.append((nome, exige_arq))
            continue
        ausentes = [c for c in exige_cols if c not in df.columns]
        if ausentes:
            print(f"    [parcial] {nome}")
            print(f"             sem as colunas {ausentes}")
            rodam += 1
            continue
        print(f"    [ sim ]  {nome}")
        rodam += 1

    print("\n" + "=" * LARGURA)
    print(f"  {rodam} de {len(ETAPAS)} etapas rodam com o que ha aqui.")
    print("=" * LARGURA)

    if bloqueadas:
        print("\n  Bloqueadas, e o que cada uma exige:\n")
        for nome, arq in bloqueadas:
            print(f"    {nome}")
            print(f"      precisa de {arq}, que so a base bruta produz.")

    print("\n  Sem a base bruta voce NAO consegue:")
    print("    - recalcular o painel (mudar mapeamento, conceito ou indicador)")
    print("    - acrescentar indicador novo")
    print("    - conferir um numero contra o relatorio de origem")
    print("\n  Com o painel que ja tem, voce CONSEGUE:")
    print("    - treinar e avaliar a rede, e comparar com os baselines")
    print("    - rodar os seis testes analiticos e a analise de sensibilidade")
    print("    - produzir a interpretacao e os quadros do TCC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
