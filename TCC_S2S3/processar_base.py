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

import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

LARGURA = 78


def _parece_ifdata(caminho: Path) -> bool:
    """O nome do arquivo carrega um período AAAAMM, como toda exportação do IF.data."""
    return bool(re.search(r"20\d{2}\D{0,2}(0[1-9]|1[0-2])(?!\d)", caminho.stem))


def _raiz_dos_csv(diretorio: Path, minimo: int = 6) -> Path | None:
    """Pasta-ancestral comum dos CSV do IF.data abaixo de ``diretorio``.

    ``consolidacao.consolidar()`` varre com ``rglob``, de modo que qualquer
    ancestral serve. Exigir profundidade exata — ano/anomes/arquivo — só cria
    falha quando a extração do zip acrescenta um nível, que é o acidente mais
    comum deste projeto.
    """
    if not diretorio.exists():
        return None
    achados = [c for c in diretorio.rglob("*.csv") if _parece_ifdata(c)]
    if len(achados) < minimo:
        return None
    comum = Path(os.path.commonpath([str(c.parent) for c in achados]))
    return comum


def localizar_base(argumento: str | None) -> Path | None:
    """Encontra a pasta da base bruta, tolerando variações de nome e de nível."""
    if argumento:
        p = Path(argumento)
        if not p.exists():
            return None
        return _raiz_dos_csv(p, minimo=1) or p

    return _raiz_dos_csv(RAIZ / "dados" / "ifdata_bruto")


def procurar_base_fora(minimo: int = 6) -> list[tuple[Path, int]]:
    """Procura a base em lugares prováveis, para orientar quem errou o destino.

    Não lê nem move nada: conta arquivos com cara de exportação do IF.data e
    devolve, por local de busca, a pasta-ancestral comum deles — que é o
    caminho a passar para ``processar_base.py``.
    """
    locais = [RAIZ, RAIZ.parent]
    for nome in ("Downloads", "Documentos", "Documents", "Desktop",
                 "Área de Trabalho", "Area de Trabalho", "OneDrive"):
        locais.append(Path.home() / nome)

    achados: list[tuple[Path, int]] = []
    ja_vistos: set[Path] = set()
    for local in locais:
        if not local.exists() or local in ja_vistos:
            continue
        ja_vistos.add(local)
        try:
            csvs = [c for c in local.rglob("*.csv") if _parece_ifdata(c)]
        except (PermissionError, OSError):
            continue
        if len(csvs) < minimo:
            continue
        comum = Path(os.path.commonpath([str(c.parent) for c in csvs]))
        achados.append((comum, len(csvs)))

    # Uma pasta ja contida em outra ja listada nao acrescenta informacao.
    achados.sort(key=lambda kv: -kv[1])
    final: list[tuple[Path, int]] = []
    for pasta, n in achados:
        if any(pasta == o or o in pasta.parents for o, _ in final):
            continue
        final.append((pasta, n))
    return final


def main() -> int:
    import pandas as pd

    from fraude_s2s3 import (consolidacao, diagnostico, indicadores,
                             segmentacao, testes_analiticos)

    print("=" * LARGURA)
    print("PROCESSAMENTO DA BASE IF.data".center(LARGURA))
    print("=" * LARGURA)

    base = localizar_base(sys.argv[1] if len(sys.argv) > 1 else None)
    if base is None:
        destino = RAIZ / "dados" / "ifdata_bruto"
        print("\n" + "=" * LARGURA)
        print("  BASE NAO ENCONTRADA — nada foi processado.".center(LARGURA))
        print("=" * LARGURA)
        print(f"\n  Procurei por arquivos .csv com periodo no nome (AAAAMM) dentro de:")
        print(f"      {destino}")
        print(f"\n  A pasta {'existe, mas sem CSV do IF.data' if destino.exists() else 'nem existe'}.")

        print("\n  Procurando a base em outros lugares da maquina...")
        candidatos = procurar_base_fora()
        if candidatos:
            print("\n  ENCONTREI arquivos com cara de exportacao do IF.data aqui:\n")
            for pasta, n in candidatos[:5]:
                print(f"      {n:>4} arquivos  ->  {pasta}")
            melhor = candidatos[0][0]
            print("\n  Duas formas de resolver:\n")
            print("  (a) Processar direto de onde esta, sem mover nada:\n")
            print(f'          python processar_base.py "{melhor}"')
            print("\n  (b) Mover o conteudo para o lugar padrao e rodar sem argumento:\n")
            print(f"          mover    {melhor}")
            print(f"          para     {destino}")
        else:
            print("  Nao achei nenhuma exportacao do IF.data na maquina.\n")
            print("  Baixe os relatorios pela interface web do IF.data seguindo")
            print("  docs/GUIA_EXTRACAO_MANUAL.md e salve em:\n")
            print(f"      {destino}")
            print("\n  A estrutura de subpastas pode ser qualquer uma: a leitura e")
            print("  recursiva. O que importa e o periodo estar no nome do arquivo,")
            print("  como em 'dados 2019-03 Ativo.csv'.")

        print("\n" + "=" * LARGURA)
        print("  Codigo de saida 2 = base nao encontrada. Nao e erro de programa.".center(LARGURA))
        print("=" * LARGURA)
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
    try:
        consolidado = consolidacao.consolidar(base, verboso=True)
    except ValueError as e:
        print("\n" + "=" * LARGURA)
        print("  BASE INCOMPLETA OU ILEGIVEL — nada foi gravado.".center(LARGURA))
        print("=" * LARGURA)
        print(f"\n  Motivo: {e}\n")
        print(f"  Pasta lida: {base}")
        print(f"  Arquivos .csv encontrados: {n_csv}")
        print("\n  O que conferir:")
        print("    1. Os arquivos sao os exportados pelo IF.data, sem edicao em")
        print("       planilha? Salvar de novo pelo Excel troca o separador e o")
        print("       cabecalho hierarquico, e a leitura deixa de reconhecer.")
        print("    2. O nome traz o periodo e o relatorio, como")
        print("       'dados 2019-03 Ativo.csv'? A leitura se orienta pelo nome.")
        print("    3. Os seis relatorios de cada trimestre estao presentes?")
        print("       Ver docs/GUIA_EXTRACAO_MANUAL.md.")
        print("\n" + "=" * LARGURA)
        print("  Codigo de saida 3 = base ilegivel. Nao e erro de programa.".center(LARGURA))
        print("=" * LARGURA)
        return 3
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
