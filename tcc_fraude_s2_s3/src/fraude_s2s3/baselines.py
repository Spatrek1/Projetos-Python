"""Referências de comparação para a rede neural.

Sem baseline, "a rede encontrou 12 instituições atípicas" não é resultado: é
uma lista. A pergunta que a banca fará — e que o TCC precisa responder — é se
a rede acrescenta algo sobre métodos mais simples e mais auditáveis.

Baselines não supervisionados (mesmo insumo, mesmo escore):
    * PCA — erro de reconstrução linear. Se o autoencoder não superar o PCA,
      a não linearidade não está comprando nada neste painel.
    * Mahalanobis — distância estatística clássica; é o "modelo linear" da
      detecção de atipicidade multivariada.
    * Isolation Forest — método de árvore, sem suposição de distribuição.

Baselines supervisionados (só com rótulo fraco e guarda de circularidade):
    * XGBoost e LightGBM — os modelos que o projeto de pesquisa já previa.
      Aqui eles não são substituídos pela rede: são o termo de comparação.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.covariance import MinCovDet
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest

from . import diagnostico

AREA = "modelagem/baselines"


def escore_pca(X_treino: np.ndarray, X_pontuar: np.ndarray,
               n_componentes: int | None = None) -> np.ndarray:
    """Erro de reconstrução de um PCA ajustado só no treino."""
    n_componentes = n_componentes or min(8, X_treino.shape[1] - 1, max(len(X_treino) - 1, 1))
    p = PCA(n_components=n_componentes, random_state=0).fit(X_treino)
    recon = p.inverse_transform(p.transform(X_pontuar))
    return ((X_pontuar - recon) ** 2).mean(axis=1)


def escore_mahalanobis(X_treino: np.ndarray, X_pontuar: np.ndarray) -> np.ndarray:
    """Distância de Mahalanobis robusta (covariância de determinante mínimo).

    A versão robusta é obrigatória aqui: a covariância amostral comum é
    estimada com os próprios pontos atípicos dentro, o que mascara a anomalia.
    """
    try:
        modelo = MinCovDet(random_state=0, support_fraction=0.9).fit(X_treino)
        return modelo.mahalanobis(X_pontuar)
    except Exception as e:
        diagnostico.registrar(
            area=AREA,
            item=f"Mahalanobis robusto falhou ({type(e).__name__}).",
            impacto="Perde-se um dos termos de comparacao com a rede.",
            acao=(
                "Em geral e matriz singular por colinearidade entre indicadores. "
                "Reduzir atributos redundantes ou aplicar PCA antes. "
                "Area: baselines.escore_mahalanobis()."
            ),
            severidade=diagnostico.Severidade.OBSERVA,
        )
        return np.full(len(X_pontuar), np.nan)


def escore_isolation_forest(X_treino: np.ndarray, X_pontuar: np.ndarray,
                            semente: int = 0) -> np.ndarray:
    modelo = IsolationForest(n_estimators=500, random_state=semente, contamination="auto")
    modelo.fit(X_treino)
    return -modelo.score_samples(X_pontuar)   # maior = mais atípico


def painel_de_escores(X_treino: np.ndarray, X_pontuar: np.ndarray,
                      escore_rede: np.ndarray | None = None) -> pd.DataFrame:
    """Junta os escores em uma tabela comparável (todos em posto percentual).

    Comparar escores brutos entre métodos não faz sentido — as escalas são
    incomparáveis. O posto percentual dentro do próprio método é a única
    comparação legítima, e é também a forma como o escore seria usado na
    prática (priorização de carga de auditoria).
    """
    colunas: dict[str, np.ndarray] = {
        "pca": escore_pca(X_treino, X_pontuar),
        "mahalanobis": escore_mahalanobis(X_treino, X_pontuar),
        "isolation_forest": escore_isolation_forest(X_treino, X_pontuar),
    }
    if escore_rede is not None:
        colunas["rede_autoencoder"] = escore_rede

    df = pd.DataFrame(colunas)
    for c in df.columns:
        df[f"posto_{c}"] = df[c].rank(pct=True)
    return df


def concordancia(df_escores: pd.DataFrame) -> pd.DataFrame:
    """Correlação de posto entre métodos.

    Leitura: concordância alta significa que a rede está redescobrindo o que o
    PCA já dizia — e então o custo de interpretabilidade da rede não se
    justifica. Concordância baixa exige explicar *o que* a rede vê a mais,
    caso a caso.
    """
    postos = df_escores[[c for c in df_escores.columns if c.startswith("posto_")]]
    return postos.corr(method="spearman")


# ---------------------------------------------------------------------------
# Supervisionados (apenas com rótulo fraco e guarda de circularidade ativa)
# ---------------------------------------------------------------------------

def treinar_gbm(X_treino: np.ndarray, y_treino: np.ndarray,
                X_teste: np.ndarray, biblioteca: str = "xgboost",
                semente: int = 0):
    """Ajusta XGBoost ou LightGBM; devolve (modelo, probabilidades).

    Mantido para preservar a comparação prevista no projeto de pesquisa entre
    XGBoost e LightGBM, agora com a rede como terceiro termo.
    """
    if len(np.unique(y_treino)) < 2:
        diagnostico.registrar(
            area=AREA,
            item="Rotulo fraco com uma unica classe no treino.",
            impacto="Modelos supervisionados nao podem ser ajustados.",
            acao=(
                "Revisar o limiar do rotulo fraco (avaliacao.rotulo_fraco) ou aceitar "
                "que o desenho e exclusivamente nao supervisionado. "
                "Area: baselines.treinar_gbm()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
        return None, np.full(len(X_teste), np.nan)

    positivos = float(np.mean(y_treino))
    peso = (1 - positivos) / max(positivos, 1e-6)

    if biblioteca == "xgboost":
        try:
            from xgboost import XGBClassifier
        except ImportError:
            diagnostico.registrar(
                area=AREA, item="xgboost nao instalado.",
                impacto="Falta o baseline previsto no projeto de pesquisa.",
                acao="pip install xgboost", severidade=diagnostico.Severidade.OBSERVA,
            )
            return None, np.full(len(X_teste), np.nan)
        modelo = XGBClassifier(
            n_estimators=400, max_depth=3, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
            scale_pos_weight=peso, random_state=semente, eval_metric="logloss",
        )
    else:
        try:
            from lightgbm import LGBMClassifier
        except ImportError:
            diagnostico.registrar(
                area=AREA, item="lightgbm nao instalado.",
                impacto="Falta o baseline previsto no projeto de pesquisa.",
                acao="pip install lightgbm", severidade=diagnostico.Severidade.OBSERVA,
            )
            return None, np.full(len(X_teste), np.nan)
        modelo = LGBMClassifier(
            n_estimators=400, max_depth=3, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
            scale_pos_weight=peso, random_state=semente, verbose=-1,
        )

    modelo.fit(X_treino, y_treino)
    return modelo, modelo.predict_proba(X_teste)[:, 1]
