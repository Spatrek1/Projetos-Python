"""Avaliação dos escores de atipicidade.

O problema central da avaliação
-------------------------------
Não existe rótulo público de fraude para bancos brasileiros. Sem rótulo não há
acurácia, não há AUC-ROC, não há F1 — as métricas listadas no projeto de
pesquisa só existem se houver contra o que comparar.

Este módulo organiza três formas legítimas de avaliar, em ordem decrescente de
força probatória:

1. **Validação por eventos públicos** (:func:`validar_por_eventos`).
   Eventos verificáveis em fonte primária — liquidação extrajudicial, regime
   de administração especial temporária, intervenção, cancelamento de
   autorização — com data. Poucos positivos, mas reais. Permite Precision@k,
   Recall@k e *antecedência* (quantos trimestres antes o escore subiu).

2. **Coerência interna** (:func:`estabilidade_temporal`,
   :func:`concordancia_metodos`). O escore é estável no tempo e entre métodos?
   Não prova detecção, mas um escore instável não serve para nada.

3. **Rótulo fraco** (:func:`rotulo_fraco`). Construído a partir dos próprios
   indicadores — útil apenas para comparar arquiteturas entre si, jamais como
   evidência de detecção de fraude. Ver :mod:`fraude_s2s3.vazamento`.

Sobre a métrica que o TCC deve reportar
---------------------------------------
Em detecção de evento raro com auditoria de recurso limitado, a métrica
pertinente não é acurácia nem AUC-ROC: é **precisão no topo da lista**
(quantas das k instituições que o auditor efetivamente visitaria eram de
fato problemáticas). AUC-ROC integra sobre toda a curva, inclusive faixas que
nenhum auditor examinaria.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import diagnostico
from .config import CONFIG

AREA = "avaliacao"


# ---------------------------------------------------------------------------
# 1. Validação por eventos públicos
# ---------------------------------------------------------------------------

@dataclass
class ResultadoEventos:
    tabela_k: pd.DataFrame
    antecedencia: pd.DataFrame
    n_eventos: int
    n_eventos_no_painel: int


def validar_por_eventos(escores: pd.DataFrame, eventos: pd.DataFrame,
                        coluna_escore: str = "escore",
                        cfg=None) -> ResultadoEventos:
    """Confronta o ranking de atipicidade com eventos públicos datados.

    ``escores``: colunas ``cod_inst``, ``anomes``, ``<coluna_escore>``.
    ``eventos``: colunas ``cod_inst``, ``anomes_evento``, ``tipo_evento``,
    ``fonte`` (URL ou referência do documento primário).

    Uma observação (instituição, trimestre) é considerada positiva quando cai
    na janela de ``janela_antecedencia`` trimestres **anteriores** ao evento.
    Trimestres posteriores ao evento são excluídos: depois da intervenção o
    balanço reflete a intervenção, e acertar aí não é previsão.
    """
    cfg_aval = (cfg or CONFIG).avaliacao
    if eventos.empty:
        diagnostico.registrar(
            area=AREA,
            item="Nenhum evento publico informado para validacao externa.",
            impacto=(
                "Sem eventos, o trabalho nao consegue afirmar que o escore tem relacao "
                "com problema real. Toda leitura fica restrita a 'atipicidade contabil', "
                "sem ponte com fraude — o que limita o alcance da conclusao."
            ),
            acao=(
                "Preencher dados/externos/eventos_publicos.csv com eventos verificaveis "
                "em fonte primaria (atos do Banco Central de liquidacao extrajudicial, "
                "RAET, intervencao, cancelamento de autorizacao; processos "
                "administrativos sancionadores; fatos relevantes na CVM). Registrar a "
                "URL de cada ato na coluna 'fonte'. Area: avaliacao.validar_por_eventos()."
            ),
            severidade=diagnostico.Severidade.BLOQUEIA,
        )
        vazio = pd.DataFrame()
        return ResultadoEventos(vazio, vazio, 0, 0)

    df = escores.copy()
    df["positivo"] = 0
    no_painel = 0
    for _, ev in eventos.iterrows():
        cod, quando = ev["cod_inst"], int(ev["anomes_evento"])
        janela = _trimestres_anteriores(quando, cfg_aval.janela_antecedencia)
        m = (df["cod_inst"].astype(str) == str(cod)) & (df["anomes"].isin(janela))
        if m.any():
            no_painel += 1
        df.loc[m, "positivo"] = 1
        # remove trimestres posteriores ao evento
        df = df[~((df["cod_inst"].astype(str) == str(cod)) & (df["anomes"] > quando))]

    if no_painel == 0:
        diagnostico.registrar(
            area=AREA,
            item="Nenhum evento informado tem correspondencia no painel.",
            impacto="A validacao externa nao pode ser executada.",
            acao=(
                "Conferir se 'cod_inst' no arquivo de eventos usa o mesmo identificador "
                "do IF.data e se a data do evento cai dentro de 2019-2024. "
                "Area: avaliacao.validar_por_eventos()."
            ),
            severidade=diagnostico.Severidade.BLOQUEIA,
        )

    df = df.sort_values(coluna_escore, ascending=False).reset_index(drop=True)
    total_pos = int(df["positivo"].sum())

    linhas = []
    for k in cfg_aval.ks:
        if k > len(df):
            continue
        topo = df.head(k)
        acertos = int(topo["positivo"].sum())
        base = total_pos / len(df) if len(df) else np.nan
        linhas.append(
            {
                "k": k,
                "precisao_em_k": acertos / k,
                "recall_em_k": acertos / total_pos if total_pos else np.nan,
                "acertos": acertos,
                "taxa_base": base,
                "ganho_sobre_acaso": (acertos / k) / base if base else np.nan,
            }
        )
    tabela_k = pd.DataFrame(linhas)

    limiar = df[coluna_escore].quantile(cfg_aval.percentil_alerta)
    ant = []
    for _, ev in eventos.iterrows():
        cod, quando = str(ev["cod_inst"]), int(ev["anomes_evento"])
        hist = escores[(escores["cod_inst"].astype(str) == cod) & (escores["anomes"] < quando)]
        acima = hist[hist[coluna_escore] >= limiar]
        ant.append(
            {
                "cod_inst": cod,
                "anomes_evento": quando,
                "tipo_evento": ev.get("tipo_evento", ""),
                "primeiro_alerta": int(acima["anomes"].min()) if len(acima) else None,
                "trimestres_de_antecedencia": (
                    _distancia_trimestres(int(acima["anomes"].min()), quando) if len(acima) else None
                ),
                "trimestres_observados_antes": len(hist),
                "fonte": ev.get("fonte", ""),
            }
        )
    antecedencia = pd.DataFrame(ant)

    if total_pos < 10:
        diagnostico.registrar(
            area=AREA,
            item=f"Apenas {total_pos} observacao(oes) positiva(s) na validacao por eventos.",
            impacto=(
                "Com esse numero, Precision@k e Recall@k tem intervalo de confianca "
                "largo demais para sustentar comparacao entre modelos. O resultado deve "
                "ser apresentado como estudo de caso, nao como avaliacao estatistica."
            ),
            acao=(
                "Ou ampliar a lista de eventos publicos verificaveis, ou reposicionar "
                "esta secao do TCC como analise qualitativa de casos. "
                "Area: avaliacao.validar_por_eventos()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
    return ResultadoEventos(tabela_k, antecedencia, len(eventos), no_painel)


def _trimestres_anteriores(anomes: int, n: int) -> list[int]:
    saida, atual = [], anomes
    for _ in range(n):
        atual = _trimestre_anterior(atual)
        saida.append(atual)
    return saida


def _trimestre_anterior(anomes: int) -> int:
    ano, mes = divmod(anomes, 100)
    mes -= 3
    if mes < 1:
        ano, mes = ano - 1, 12
    return ano * 100 + mes


def _distancia_trimestres(a: int, b: int) -> int:
    ano_a, mes_a = divmod(a, 100)
    ano_b, mes_b = divmod(b, 100)
    return (ano_b * 4 + (mes_b - 1) // 3) - (ano_a * 4 + (mes_a - 1) // 3)


# ---------------------------------------------------------------------------
# 2. Coerência interna
# ---------------------------------------------------------------------------

def estabilidade_temporal(escores: pd.DataFrame, coluna: str = "escore") -> pd.DataFrame:
    """Correlação de posto do escore entre trimestres consecutivos.

    Fraude contábil é fenômeno persistente: o escore deveria ser
    razoavelmente estável de um trimestre para o outro. Correlação próxima de
    zero indica que o escore está medindo ruído trimestral, não condição da
    instituição.
    """
    from scipy.stats import spearmanr

    periodos = sorted(escores["anomes"].unique())
    linhas = []
    for anterior, atual in zip(periodos[:-1], periodos[1:]):
        a = escores[escores["anomes"] == anterior].set_index("cod_inst")[coluna]
        b = escores[escores["anomes"] == atual].set_index("cod_inst")[coluna]
        comum = a.index.intersection(b.index)
        rho = spearmanr(a.loc[comum], b.loc[comum]).statistic if len(comum) >= 5 else np.nan
        linhas.append({"de": anterior, "para": atual, "n_comum": len(comum), "spearman": rho})
    tabela = pd.DataFrame(linhas)

    media = tabela["spearman"].mean()
    if np.isfinite(media) and media < 0.3:
        diagnostico.registrar(
            area=AREA,
            item=f"Persistencia trimestral do escore baixa (Spearman medio = {media:.2f}).",
            impacto=(
                "Um escore que muda de ordenacao a cada trimestre nao descreve condicao "
                "da instituicao. Ou os indicadores estao dominados por sazonalidade, ou "
                "o modelo esta capturando ruido."
            ),
            acao=(
                "Verificar se os indicadores usam variacao interanual (nao trimestral) e "
                "se ha efeito de dezembro no painel. Area: avaliacao.estabilidade_temporal()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
    return tabela


def concordancia_metodos(df_escores: pd.DataFrame) -> pd.DataFrame:
    """Concordância entre rede e baselines (delegado a baselines.concordancia)."""
    from .baselines import concordancia

    return concordancia(df_escores)


# ---------------------------------------------------------------------------
# 3. Rótulo fraco (uso restrito)
# ---------------------------------------------------------------------------

def rotulo_fraco(indicadores: pd.DataFrame, componentes: list[str],
                 percentil: float = 0.90) -> tuple[np.ndarray, set[str]]:
    """Rótulo binário construído a partir de um subconjunto de indicadores.

    Devolve ``(rotulo, componentes_usados)``. O segundo elemento alimenta a
    :class:`fraude_s2s3.vazamento.GuardaCircularidade`: qualquer atributo
    derivado desses componentes precisa sair do conjunto de entrada, sob pena
    de o modelo apenas reconstruir a própria definição do rótulo.

    Este rótulo **não é fraude**. É "combinação atípica de sinais contábeis
    de risco". Toda métrica calculada contra ele mede concordância com uma
    regra construída pelo autor, e assim deve ser nomeada no TCC.
    """
    presentes = [c for c in componentes if c in indicadores.columns]
    ausentes = [c for c in componentes if c not in indicadores.columns]
    if ausentes:
        diagnostico.registrar(
            area=AREA,
            item=f"Componentes do rotulo fraco ausentes: {ausentes}.",
            impacto="O rotulo muda de definicao em relacao ao descrito na metodologia.",
            acao=(
                "Ajustar a lista de componentes ou completar a coleta. "
                "Area: avaliacao.rotulo_fraco()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
    if not presentes:
        return np.zeros(len(indicadores)), set()

    z = indicadores[presentes].apply(
        lambda s: (s - s.median()) / ((s - s.median()).abs().median() * 1.4826 or 1)
    )
    composto = z.abs().mean(axis=1)
    limiar = composto.quantile(percentil)

    diagnostico.registrar(
        area=AREA,
        item=(
            f"Rotulo fraco definido pelo percentil {percentil:.0%} de um composto de "
            f"{len(presentes)} indicador(es)."
        ),
        impacto=(
            "Toda metrica supervisionada deste trabalho e medida contra uma regra "
            "construida pelo proprio autor, nao contra fraude verificada. Reportar "
            "'acuracia' ou 'AUC' sem essa qualificacao seria afirmar mais do que o "
            "desenho permite — e e exatamente o ponto em que replicacoes do artigo de "
            "referencia costumam derrapar."
        ),
        acao=(
            "No TCC, nomear a metrica como 'concordancia com o rotulo fraco' e nao como "
            "'deteccao de fraude'. Area: avaliacao.rotulo_fraco()."
        ),
        severidade=diagnostico.Severidade.COMPROMETE,
    )
    return (composto >= limiar).astype(int).to_numpy(), set(presentes)


# ---------------------------------------------------------------------------
# Métricas de classificação (quando houver rótulo)
# ---------------------------------------------------------------------------

def metricas_classificacao(y: np.ndarray, escore: np.ndarray,
                           limiar: float | None = None) -> dict:
    """Conjunto de métricas equivalente ao reportado no artigo de referência.

    Inclui acurácia balanceada e Kappa porque, com evento raro, a acurácia
    simples é satisfeita por um classificador que nunca sinaliza nada.
    """
    from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                                 cohen_kappa_score, f1_score, log_loss,
                                 precision_score, recall_score, roc_auc_score)

    y = np.asarray(y).astype(int)
    escore = np.asarray(escore, dtype=float)
    valido = np.isfinite(escore)
    y, escore = y[valido], escore[valido]
    if len(np.unique(y)) < 2:
        return {"erro": "rotulo com uma unica classe; metricas indefinidas"}

    if limiar is None:
        limiar = _limiar_maximiza_f1(y, escore)
    pred = (escore >= limiar).astype(int)

    p = (escore - escore.min()) / (np.ptp(escore) or 1)
    return {
        "acuracia": accuracy_score(y, pred),
        "acuracia_balanceada": balanced_accuracy_score(y, pred),
        "kappa": cohen_kappa_score(y, pred),
        "precisao": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, zero_division=0),
        "auc_roc": roc_auc_score(y, escore),
        "log_loss": log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)),
        "limiar": float(limiar),
        "taxa_base_positivos": float(y.mean()),
    }


def _limiar_maximiza_f1(y: np.ndarray, escore: np.ndarray) -> float:
    """Limiar que maximiza F1, como em Benyasrisawat e Ounlert (2026)."""
    from sklearn.metrics import f1_score

    candidatos = np.quantile(escore, np.linspace(0.5, 0.999, 120))
    melhor, melhor_f1 = candidatos[0], -1.0
    for c in candidatos:
        f = f1_score(y, (escore >= c).astype(int), zero_division=0)
        if f > melhor_f1:
            melhor, melhor_f1 = c, f
    return float(melhor)
