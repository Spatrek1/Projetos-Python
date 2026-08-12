"""Interpretação dos escores: de "atípico" para "atípico em quê".

Um escore sem explicação é inútil para auditoria. O auditor não pode abrir um
procedimento com "o modelo deu 0,93"; precisa de uma afirmação testável do
tipo "a provisão caiu enquanto a carteira E-H subiu".

Duas rotas, ambas implementadas aqui:

``decompor_erro``
    Para autoencoder, a decomposição é direta e exata: o erro de reconstrução
    é soma dos erros por atributo. Não é aproximação — diferente de SHAP, que
    estima. É a principal vantagem prática de usar autoencoder em auditoria.

``gradientes_integrados``
    Para a cabeça supervisionada, atribuição por Integrated Gradients
    (Sundararajan, Taly e Yan, 2017), com linha de base no vetor nulo, que
    após a normalização corresponde à instituição mediana do trimestre.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import torch
    TORCH_DISPONIVEL = True
except ImportError:  # pragma: no cover
    TORCH_DISPONIVEL = False


def decompor_erro(erro_por_atributo: np.ndarray, atributos: list[str],
                  indice: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """Para cada observação, os atributos que mais contribuíram para o erro.

    Devolve formato longo, pronto para virar quadro no TCC: uma linha por
    (instituição, trimestre, atributo) entre os ``top`` maiores contribuintes,
    com a participação percentual no erro total.
    """
    total = erro_por_atributo.sum(axis=1, keepdims=True)
    participacao = np.divide(erro_por_atributo, np.where(total == 0, np.nan, total))

    linhas = []
    for i in range(erro_por_atributo.shape[0]):
        ordem = np.argsort(-erro_por_atributo[i])[:top]
        for posicao, j in enumerate(ordem, start=1):
            linhas.append(
                {
                    "cod_inst": indice.iloc[i]["cod_inst"],
                    "anomes": indice.iloc[i]["anomes"],
                    "posicao": posicao,
                    "atributo": atributos[j],
                    "erro": float(erro_por_atributo[i, j]),
                    "participacao_no_erro": float(participacao[i, j]),
                }
            )
    return pd.DataFrame(linhas)


def perfil_por_instituicao(decomposicao: pd.DataFrame, cod_inst: str) -> pd.DataFrame:
    """Trajetória dos motivos de atipicidade de uma instituição ao longo do tempo.

    É a visão que o auditor usa: não "quem é atípico", mas "por que esta ficou
    atípica e desde quando".
    """
    d = decomposicao[decomposicao["cod_inst"].astype(str) == str(cod_inst)]
    if d.empty:
        return d
    return (
        d.pivot_table(index="anomes", columns="atributo",
                      values="participacao_no_erro", aggfunc="max")
        .fillna(0.0)
        .sort_index()
    )


def ranking_atributos(decomposicao: pd.DataFrame) -> pd.DataFrame:
    """Quais indicadores explicam a atipicidade no agregado da amostra.

    Se o topo for dominado pelos indicadores prudenciais propostos
    (provisão, Basileia, crédito tributário), o trabalho tem argumento de que
    a adaptação ao contexto bancário foi o que produziu a informação — e não a
    simples transposição dos modelos de empresa não financeira.
    """
    return (
        decomposicao.groupby("atributo")
        .agg(
            vezes_no_topo=("atributo", "size"),
            participacao_media=("participacao_no_erro", "mean"),
            erro_medio=("erro", "mean"),
        )
        .sort_values("vezes_no_topo", ascending=False)
        .reset_index()
    )


def gradientes_integrados(modelo, x: np.ndarray, atributos: list[str],
                          passos: int = 64) -> pd.DataFrame:
    """Atribuição por Integrated Gradients para a cabeça de classificação."""
    if not TORCH_DISPONIVEL:
        raise ImportError("PyTorch necessario para gradientes integrados.")

    modelo.eval()
    entrada = torch.tensor(x, dtype=torch.float32)
    base = torch.zeros_like(entrada)
    total = torch.zeros_like(entrada)

    for passo in range(1, passos + 1):
        alfa = passo / passos
        ponto = (base + alfa * (entrada - base)).clone().requires_grad_(True)
        saida = modelo(ponto)
        logit = saida[1] if isinstance(saida, tuple) else saida
        logit.sum().backward()
        total = total + ponto.grad

    atribuicao = ((entrada - base) * total / passos).detach().numpy()
    return pd.DataFrame(atribuicao, columns=atributos)


def narrativa(decomposicao: pd.DataFrame, cod_inst: str, anomes: int,
              catalogo: pd.DataFrame | None = None, top: int = 3) -> str:
    """Frase auditável a partir da decomposição do erro.

    Deliberadamente redigida em termos de *atipicidade*, nunca de fraude: o que
    o modelo produz é hipótese a testar, e o texto precisa carregar essa
    distinção para não induzir conclusão que os dados não sustentam.
    """
    d = decomposicao[
        (decomposicao["cod_inst"].astype(str) == str(cod_inst))
        & (decomposicao["anomes"] == anomes)
    ].nsmallest(top, "posicao")
    if d.empty:
        return f"Sem decomposicao disponivel para {cod_inst} em {anomes}."

    leituras = {}
    if catalogo is not None and "indicador" in catalogo.columns:
        leituras = dict(zip(catalogo["indicador"], catalogo.get("leitura_de_risco", "")))

    partes = []
    for _, r in d.iterrows():
        base = str(r["atributo"]).replace("z_par_", "").replace("faltante_", "")
        contexto = leituras.get(base, "")
        partes.append(
            f"{base} ({r['participacao_no_erro']:.0%} do erro)"
            + (f" — {contexto}" if contexto else "")
        )
    return (
        f"Instituicao {cod_inst}, {anomes}: o comportamento observado difere do padrao "
        f"dos pares principalmente em {'; '.join(partes)}. "
        "Trata-se de hipotese de trabalho para direcionamento de procedimento de "
        "auditoria, nao de indicio de irregularidade."
    )
