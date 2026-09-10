"""Processa a base bruta do IF.data e grava os arquivos tratados.

Uso
---
    cd "C:\\Documentos\\Projetos-Python\\TCC_S2S3"
    python processar_base.py

Procura a base em ``dados/ifdata_bruto/`` automaticamente. Para apontar outro lugar::

    python processar_base.py "D:\\algum\\outro\\caminho\\IF DATA BASE"

Saída
-----
Grava em ``dados/tratados/``:

    painel_conceitos_completo.csv   todas as instituições, todos os conceitos
    painel_conceitos_S2S3.csv       recorte da pesquisa
    painel_indicadores_S2S3.csv     os indicadores, prontos para a modelagem
    cobertura_conceitos.csv         ausência por conceito
    inventario_arquivos.csv         o que foi lido, e de onde
    quadro_operacionalizacao.csv    anexo do TCC
    pontos_de_correcao.csv          pendências desta execução

E em ``dados/externos/segmentacao_oficial.csv`` o enquadramento S1–S5 extraído
da coluna SR dos próprios relatórios.

Nenhum valor é criado, imputado ou alterado. Conta ausente permanece ausente e
aparece no relatório de pendências.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

LARGURA = 78


def localizar_base(argumento: str | None) -> Path | None:
    """Encontra a pasta da base bruta, tolerando variações de nome."""
    if argumento:
        p = Path(argumento)
        return p if p.exists() else None

    brutos = RAIZ / "dados" / "ifdata_bruto"
    if not brutos.exists():
        return None

    # A base é a pasta que contém subpastas de ano com CSVs dentro.
    candidatas = [d for d in brutos.iterdir()
                  if d.is_dir() and any(d.glob("*/*/*.csv"))]
    if candidatas:
        return candidatas[0]
    # Ou os anos podem estar diretamente em dados/ifdata_bruto.
    if any(brutos.glob("*/*/*.csv")):
        return brutos
    return None


def main() -> int:
    import pandas as pd

    from fraude_s2s3 import (consolidacao, diagnostico, indicadores,
                             segmentacao, testes_analiticos)

    print("=" * LARGURA)
    print("PROCESSAMENTO DA BASE IF.data".center(LARGURA))
    print("=" * LARGURA)

    base = localizar_base(sys.argv[1] if len(sys.argv) > 1 else None)
    if base is None:
        print("\n  Base nao encontrada.")
        print(f"\n  Esperado em: {RAIZ / 'dados' / 'ifdata_bruto'}")
        print("\n  Estrutura esperada:")
        print("      dados\\ifdata_bruto\\IF DATA BASE\\2019\\201903\\dados 2019-03 Ativo.csv")
        print("                                \\2019\\201906\\...")
        print("\n  Ou informe o caminho:")
        print('      python processar_base.py "D:\\caminho\\IF DATA BASE"')
        return 2

    n_csv = len(list(base.rglob("*.csv")))
    print(f"\n  Base: {base}")
    print(f"  Arquivos CSV encontrados: {n_csv}")
    if n_csv < 100:
        print(f"\n  ATENCAO: esperados 144 arquivos (24 trimestres x 6 relatorios).")
        print("  Prosseguindo com o que ha; as ausencias serao reportadas ao final.")

    diagnostico.limpar()

    print("\n" + "-" * LARGURA)
    print("1. Leitura dos relatorios")
    print("-" * LARGURA)
    consolidado = consolidacao.consolidar(base, verboso=True)
    painel = consolidado.conceitos
    print(f"\n  Painel completo: {len(painel):,} observacoes, "
          f"{painel['cod_inst'].nunique():,} instituicoes, "
          f"{painel['anomes'].nunique()} trimestres")

    print("\n" + "-" * LARGURA)
    print("2. Segmentacao oficial (coluna SR)")
    print("-" * LARGURA)
    seg = segmentacao.extrair_do_resumo(
        painel, coluna_segmento="SR", coluna_inst="cod_inst", salvar=False)
    resumo_seg = seg.groupby("segmento")["cod_inst"].nunique()
    for s, n in resumo_seg.items():
        print(f"    {s}  {n:>5} instituicoes")

    alvo = painel[painel["SR"].isin(("S2", "S3"))].copy()
    alvo["segmento"] = alvo["SR"]
    print(f"\n  Amostra S2/S3: {len(alvo):,} observacoes, "
          f"{alvo['cod_inst'].nunique()} instituicoes")

    print("\n" + "-" * LARGURA)
    print("3. Indicadores")
    print("-" * LARGURA)
    ind = indicadores.construir(alvo)
    print(f"  Construidos: {len(ind.attrs['indicadores_construidos'])}")
    if ind.attrs["indicadores_ausentes"]:
        print(f"  Ausentes   : {ind.attrs['indicadores_ausentes']}")

    if "piso_basileia_aplicado" in ind.columns:
        print("\n  Piso de Basileia aplicado:")
        for piso, g in ind.groupby("piso_basileia_aplicado"):
            print(f"    {piso:>5.1f} p.p.  ->  {len(g):>5} obs, "
                  f"{g['cod_inst'].nunique():>3} instituicoes")
        if "basileia_zona_incerta" in ind.columns:
            z = int(ind["basileia_zona_incerta"].sum())
            if z:
                print(f"    zona de incerteza da faixa: {z} observacoes")

    print("\n" + "-" * LARGURA)
    print("4. Gravacao")
    print("-" * LARGURA)
    saida = RAIZ / "dados" / "tratados"
    externos = RAIZ / "dados" / "externos"
    saida.mkdir(parents=True, exist_ok=True)
    externos.mkdir(parents=True, exist_ok=True)

    # Testes analiticos: os seis procedimentos substantivos, um por parametro
    # obrigatorio. Independem de treino, particao e semente, e por isso rodam
    # aqui — o resultado e reproduzivel por qualquer terceiro a partir da base.
    sinal = testes_analiticos.aplicar(ind)
    foco = testes_analiticos.foco_de_exame(sinal)

    arquivos = {
        saida / "testes_analiticos_sinalizacoes.csv": sinal,
        saida / "testes_analiticos_foco_de_exame.csv": foco,
        saida / "testes_analiticos_resumo.csv": testes_analiticos.resumo(sinal),
        saida / "testes_analiticos_persistencia.csv":
            testes_analiticos.classificar_persistencia(sinal),
        saida / "testes_analiticos_sensibilidade.csv":
            testes_analiticos.sensibilidade(ind),
        saida / "quadro_testes_analiticos.csv": testes_analiticos.catalogo_df(),
        saida / "painel_conceitos_completo.csv": painel,
        saida / "painel_conceitos_S2S3.csv": alvo,
        saida / "painel_indicadores_S2S3.csv": ind,
        saida / "cobertura_conceitos.csv": consolidado.cobertura,
        saida / "inventario_arquivos.csv": consolidado.inventario,
        saida / "quadro_operacionalizacao.csv": indicadores.catalogo_df(),
        saida / "pontos_de_correcao.csv": diagnostico.para_dataframe(),
        externos / "segmentacao_oficial.csv": seg,
    }
    for caminho, quadro in arquivos.items():
        quadro.to_csv(caminho, index=False, encoding="utf-8-sig")
        print(f"    {caminho.relative_to(RAIZ)}  ({caminho.stat().st_size:,} bytes)")

    print("\n  Testes analiticos (limiar "
          f"{testes_analiticos.LIMIAR_PADRAO} desvios frente aos pares):")
    print(testes_analiticos.resumo(sinal).to_string(index=False))
    print(f"\n  Foco de exame apos excluir sinalizacao estrutural: {len(foco)} "
          f"observacoes de {foco['cod_inst'].nunique()} instituicoes.")

    print("\n" + diagnostico.relatorio(largura=LARGURA))

    print("\nProximo passo: abrir notebooks/00_pipeline_s2_s3.ipynb e seguir da secao 7,")
    print("carregando dados/tratados/painel_indicadores_S2S3.csv.")
    return 1 if diagnostico.ha_bloqueio() else 0


if __name__ == "__main__":
    raise SystemExit(main())
