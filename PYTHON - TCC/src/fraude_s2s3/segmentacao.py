"""Identificação dos segmentos S2 e S3 (Resolução CMN nº 4.553/2017).

Ordem de precedência adotada
----------------------------
1. **Lista oficial** de segmentação, quando fornecida em
   ``dados/externos/segmentacao_oficial.csv``. É a única fonte que produz
   classificação *idêntica* à do supervisor.
2. **Regra da norma**, calculada a partir de Exposição/PIB. É reconstrução,
   não é a classificação oficial: a norma considera exposição (incluindo
   posições fora do balanço) e atuação internacional, e o enquadramento é
   revisto em datas-base definidas pelo BCB, com transições que não coincidem
   necessariamente com o trimestre em que a razão cruza o limiar.

O caminho 2 existe para permitir que o pipeline rode ponta a ponta; **não**
substitui o caminho 1 no texto final do TCC. O módulo registra isso como
ponto de correção sempre que a regra for usada.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import diagnostico
from .config import DIR_EXTERNOS, FAIXAS_SEGMENTO, SEGMENTOS_ALVO

AREA = "segmentacao/S2-S3"

ARQUIVO_OFICIAL = DIR_EXTERNOS / "segmentacao_oficial.csv"
ARQUIVO_PIB = DIR_EXTERNOS / "pib_trimestral.csv"


def carregar_oficial(caminho: Path | str = ARQUIVO_OFICIAL) -> pd.DataFrame | None:
    """Lê a lista oficial de segmentação, se existir.

    Formato esperado (uma linha por instituição e data-base):
        ``cod_inst,anomes,segmento`` — com ``segmento`` em {S1..S5}.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        return None
    df = pd.read_csv(caminho, dtype={"cod_inst": str})
    faltando = {"cod_inst", "anomes", "segmento"} - set(df.columns)
    if faltando:
        diagnostico.registrar(
            area=AREA,
            item=f"segmentacao_oficial.csv sem colunas {sorted(faltando)}.",
            impacto="A lista oficial e ignorada e o pipeline recai na regra Exposicao/PIB.",
            acao="Ajustar o arquivo para o formato cod_inst,anomes,segmento.",
            severidade=diagnostico.Severidade.COMPROMETE,
        )
        return None
    df["segmento"] = df["segmento"].str.upper().str.strip()
    return df


def extrair_do_resumo(resumo: pd.DataFrame, coluna_segmento: str | None = None,
                      coluna_inst: str | None = None,
                      salvar: bool = True) -> pd.DataFrame:
    """Constrói a segmentação oficial a partir do relatório Resumo do IF.data.

    O relatório Resumo publica uma coluna de segmentação (rotulada ``SR`` na
    interface web) com o enquadramento S1–S5 vigente na data-base. Essa é a
    **classificação do supervisor**, não uma reconstrução: dispensa a série de
    PIB e elimina a aproximação da regra Exposição/PIB.

    Devolve, e opcionalmente grava em ``dados/externos/segmentacao_oficial.csv``,
    uma tabela ``cod_inst, anomes, segmento``.
    """
    df = resumo.copy()

    if coluna_segmento is None:
        coluna_segmento = _primeira_coluna(df, r"^sr$|^segment|segmentacao|^seg$")
    if coluna_inst is None:
        coluna_inst = _primeira_coluna(df, r"^codinst|^cod_inst|^instituicao|^cnpj")

    if coluna_segmento is None or coluna_inst is None:
        diagnostico.registrar(
            area=AREA,
            item=(
                "Nao foi possivel localizar a coluna de segmentacao ou de instituicao "
                f"no relatorio Resumo. Colunas disponiveis: {list(df.columns)[:20]}"
            ),
            impacto="A segmentacao oficial nao pode ser extraida; o pipeline recai na regra Exposicao/PIB.",
            acao=(
                "Informar explicitamente os nomes: segmentacao.extrair_do_resumo("
                "resumo, coluna_segmento='SR', coluna_inst='CodInst'). "
                "Area: segmentacao.extrair_do_resumo()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
        raise ValueError("Colunas de segmento/instituicao nao localizadas no Resumo.")

    if "anomes" not in df.columns:
        raise ValueError("O DataFrame precisa da coluna 'anomes'.")

    saida = (
        df[[coluna_inst, "anomes", coluna_segmento]]
        .rename(columns={coluna_inst: "cod_inst", coluna_segmento: "segmento"})
        .dropna(subset=["segmento"])
    )
    saida["cod_inst"] = saida["cod_inst"].astype(str).str.strip()
    saida["segmento"] = (
        saida["segmento"].astype(str).str.strip().str.upper()
        .str.extract(r"(S[1-5])", expand=False)
    )

    invalidos = int(saida["segmento"].isna().sum())
    saida = saida.dropna(subset=["segmento"]).drop_duplicates(["cod_inst", "anomes"])

    if invalidos:
        diagnostico.registrar(
            area=AREA,
            item=f"{invalidos} registro(s) do Resumo com valor de segmento fora do padrao S1-S5.",
            impacto="Essas instituicoes ficam sem enquadramento e saem da amostra.",
            acao=(
                f"Inspecionar os valores distintos da coluna '{coluna_segmento}' e ajustar "
                "a extracao. Area: segmentacao.extrair_do_resumo()."
            ),
            severidade=diagnostico.Severidade.OBSERVA,
        )

    if salvar:
        ARQUIVO_OFICIAL.parent.mkdir(parents=True, exist_ok=True)
        saida.to_csv(ARQUIVO_OFICIAL, index=False)

    return saida.reset_index(drop=True)


def _primeira_coluna(df: pd.DataFrame, padrao: str) -> str | None:
    import re
    import unicodedata

    def norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", str(s))
        s = "".join(c for c in s if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]", "", s.lower())

    for c in df.columns:
        if re.search(padrao, norm(c)):
            return c
    return None


def carregar_pib(caminho: Path | str = ARQUIVO_PIB) -> pd.Series | None:
    """PIB acumulado em 12 meses, em R$, indexado por AAAAMM.

    Fonte sugerida: IBGE (Contas Nacionais Trimestrais) ou séries do SGS/BCB.
    A escolha da série **muda o denominador** e, portanto, muda quem entra em
    S2 e em S3 — registrar a série exata usada no TCC.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        return None
    df = pd.read_csv(caminho)
    col_p = next((c for c in df.columns if "anomes" in c.lower() or "period" in c.lower()), None)
    col_v = next((c for c in df.columns if c != col_p), None)
    if col_p is None or col_v is None:
        return None
    return pd.Series(df[col_v].values, index=df[col_p].astype(int).values, name="pib")


def classificar_por_regra(painel: pd.DataFrame, pib: pd.Series) -> pd.DataFrame:
    """Aplica os limiares de Exposição/PIB da Res. 4.553/2017.

    Aproxima "exposição" pelo **ativo total**. É aproximação por baixo: a norma
    soma exposições fora do balanço, que o ativo contábil não captura.
    """
    if "ativo_total" not in painel.columns:
        raise ValueError("classificar_por_regra exige a coluna 'ativo_total'.")

    df = painel.copy()
    df["pib"] = df["anomes"].map(pib)
    sem_pib = int(df["pib"].isna().sum())
    df["razao_exposicao_pib"] = df["ativo_total"] / df["pib"]

    faixas = sorted(FAIXAS_SEGMENTO.items(), key=lambda kv: -kv[1][0])
    df["segmento"] = np.nan
    for nome, (inf, sup) in faixas:
        m = (df["razao_exposicao_pib"] >= inf) & (df["razao_exposicao_pib"] < sup)
        df.loc[m & df["segmento"].isna(), "segmento"] = nome

    diagnostico.registrar(
        area=AREA,
        item="Segmentacao S2/S3 reconstruida pela regra Exposicao/PIB, sem lista oficial.",
        impacto=(
            "A composicao da amostra pode divergir da classificacao do supervisor. "
            "Instituicoes proximas dos limiares (1% e 0,1% do PIB) podem trocar de "
            "segmento entre trimestres, criando entrada e saida artificiais no painel. "
            "Como o estudo compara S2 e S3, um erro de enquadramento contamina "
            "diretamente a comparacao entre segmentos."
        ),
        acao=(
            "Obter a lista oficial de enquadramento por data-base junto ao Banco Central "
            "e salva-la em dados/externos/segmentacao_oficial.csv "
            "(colunas: cod_inst, anomes, segmento). "
            "Area: segmentacao.carregar_oficial()."
        ),
        severidade=diagnostico.Severidade.BLOQUEIA,
    )
    if sem_pib:
        diagnostico.registrar(
            area=AREA,
            item=f"{sem_pib} observacao(oes) sem PIB correspondente no periodo.",
            impacto="Essas observacoes ficam sem segmento e saem da amostra.",
            acao="Completar dados/externos/pib_trimestral.csv para todo o recorte 2019-2024.",
            severidade=diagnostico.Severidade.COMPROMETE,
        )
    return df


def estabilizar(df: pd.DataFrame, min_trimestres: int = 4) -> pd.DataFrame:
    """Reduz oscilação de enquadramento perto dos limiares.

    Atribui a cada instituição o segmento **modal** observado, exigindo um
    mínimo de trimestres. Evita que uma instituição entre e saia da amostra a
    cada trimestre por variação marginal do ativo.
    """
    contagem = (
        df.dropna(subset=["segmento"])
        .groupby(["cod_inst", "segmento"])
        .size()
        .rename("n")
        .reset_index()
    )
    modal = (
        contagem.sort_values(["cod_inst", "n"], ascending=[True, False])
        .drop_duplicates("cod_inst")
        .set_index("cod_inst")
    )
    instaveis = contagem.groupby("cod_inst").size()
    instaveis = instaveis[instaveis > 1].index.tolist()

    saida = df.copy()
    saida["segmento_periodo"] = saida["segmento"]
    saida["segmento"] = saida["cod_inst"].map(modal["segmento"])
    saida.loc[saida["cod_inst"].map(modal["n"]).fillna(0) < min_trimestres, "segmento"] = np.nan

    if instaveis:
        diagnostico.registrar(
            area=AREA,
            item=f"{len(instaveis)} instituicao(oes) mudaram de segmento dentro do recorte.",
            impacto=(
                "A comparacao entre S2 e S3 pressupoe grupos estaveis. Instituicoes de "
                "fronteira foram fixadas no segmento modal, o que e uma decisao do "
                "pesquisador, nao da norma."
            ),
            acao=(
                "Decidir com o orientador entre: (a) segmento variavel no tempo, "
                "(b) segmento modal fixo (adotado aqui), ou (c) exclusao das instituicoes "
                "de fronteira. Documentar a escolha na secao 3.2.1. "
                f"Instituicoes afetadas: {instaveis[:10]}"
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
    return saida


def aplicar(painel: pd.DataFrame, pib: pd.Series | None = None,
            segmentos: tuple[str, ...] = SEGMENTOS_ALVO) -> pd.DataFrame:
    """Anexa o segmento e filtra o painel para S2/S3."""
    oficial = carregar_oficial()
    if oficial is not None:
        df = painel.merge(oficial, on=["cod_inst", "anomes"], how="left")
        faltantes = int(df["segmento"].isna().sum())
        if faltantes:
            diagnostico.registrar(
                area=AREA,
                item=f"{faltantes} observacao(oes) sem correspondencia na lista oficial.",
                impacto="Instituicoes sem enquadramento sao descartadas da amostra.",
                acao=(
                    "Verificar se o identificador usado na lista oficial e o mesmo codigo "
                    "de instituicao do IF.data (codigo do conglomerado x CNPJ da "
                    "instituicao individual). Area: segmentacao.aplicar()."
                ),
                severidade=diagnostico.Severidade.COMPROMETE,
            )
    else:
        pib = pib if pib is not None else carregar_pib()
        if pib is None:
            diagnostico.registrar(
                area=AREA,
                item="Nem lista oficial de segmentacao, nem serie de PIB disponiveis.",
                impacto="Nao ha como delimitar S2/S3. O escopo declarado do estudo nao pode ser cumprido.",
                acao=(
                    "Fornecer dados/externos/segmentacao_oficial.csv (preferencial) ou "
                    "dados/externos/pib_trimestral.csv. Area: segmentacao.aplicar()."
                ),
                severidade=diagnostico.Severidade.BLOQUEIA,
            )
            raise ValueError("Segmentacao indisponivel: ver pontos de correcao.")
        df = classificar_por_regra(painel, pib)

    df = estabilizar(df)
    filtrado = df[df["segmento"].isin(segmentos)].copy()

    resumo = filtrado.groupby("segmento")["cod_inst"].nunique().to_dict()
    if len(filtrado) == 0:
        diagnostico.registrar(
            area=AREA,
            item="Nenhuma instituicao classificada em S2 ou S3 apos a filtragem.",
            impacto="Pipeline sem amostra.",
            acao="Revisar identificadores e a serie de PIB. Area: segmentacao.aplicar().",
            severidade=diagnostico.Severidade.BLOQUEIA,
        )
    else:
        for seg in segmentos:
            n = resumo.get(seg, 0)
            if n < 5:
                diagnostico.registrar(
                    area=AREA,
                    item=f"Segmento {seg} com apenas {n} instituicao(oes) distintas.",
                    impacto=(
                        "Com esse tamanho nao ha base para inferencia comparativa entre "
                        "segmentos; qualquer diferenca observada e compativel com ruido "
                        "amostral. Modelos neurais sao especialmente sensiveis."
                    ),
                    acao=(
                        "Considerar: (a) usar conglomerado prudencial em vez de instituicao "
                        "individual, ampliando a cobertura; (b) tratar S2 como grupo de "
                        "referencia descritivo, sem teste estatistico; (c) revisar o "
                        "recorte com o orientador. Area: segmentacao.aplicar()."
                    ),
                    severidade=diagnostico.Severidade.COMPROMETE,
                )
    filtrado.attrs["instituicoes_por_segmento"] = resumo
    return filtrado
