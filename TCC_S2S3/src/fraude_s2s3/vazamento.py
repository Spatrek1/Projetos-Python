"""Guarda de circularidade entre atributos e rótulo.

O problema que este módulo resolve
----------------------------------
Benyasrisawat e Ounlert (2026) treinam XGBoost para prever o DF-Score usando
como atributos os **próprios componentes do DF-Score** (RSST_ACC, CH_REC,
CH_INV, SOFT_ASSETS, CH_CS, CH_CM, CH_ROA, CH_FCF — Tabela 3 do artigo), já
que DF-Score é definido como a soma deles. O resultado reportado (acurácia
0,995 e AUC-ROC 0,999, Tabela 5) é compatível com isso: o modelo não está
aprendendo a detectar fraude, está reaprendendo uma identidade aritmética que
lhe foi dada de entrada.

Isso não invalida o artigo — o objeto dele é a relação entre risco de fraude
e opinião de auditoria, estimada depois por IV-2SLS. Mas invalida a leitura de
que "AUC 0,999 mostra que o modelo detecta fraude". Replicar o desenho sem
essa observação transportaria um artefato para o TCC.

O que a guarda faz
------------------
Antes de qualquer treino supervisionado, verifica se algum atributo é
componente algébrico do rótulo (ou dele derivado por transformação monotônica
registrada) e **interrompe** o treino se for. Rótulo construído a partir de
contas contábeis só pode ser previsto por atributos que não o compõem.

Uso típico::

    guarda = GuardaCircularidade(componentes_do_rotulo={"delta_roa", "soft_assets", ...})
    atributos_limpos = guarda.filtrar(atributos)      # ou .exigir_limpo(atributos)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import diagnostico

AREA = "validade/circularidade"


class VazamentoDetectado(RuntimeError):
    """Erro deliberado: melhor falhar do que reportar métrica inflada."""


#: Prefixos gerados pelo pipeline que preservam a identidade do indicador de
#: origem (um z-score de X continua sendo X para efeito de circularidade).
PREFIXOS_DERIVADOS = ("z_par_", "faltante_", "d1_", "d4_", "rank_")


def raiz_do_atributo(nome: str) -> str:
    """Remove prefixos de derivação e devolve o indicador de origem."""
    anterior = None
    atual = nome
    while atual != anterior:
        anterior = atual
        for p in PREFIXOS_DERIVADOS:
            if atual.startswith(p):
                atual = atual[len(p):]
    return atual


@dataclass
class GuardaCircularidade:
    """Impede que componentes do rótulo entrem como atributos."""

    componentes_do_rotulo: set[str]
    nome_do_rotulo: str = "rotulo"
    tolerancia_correlacao: float = 0.98
    _violacoes: list[str] = field(default_factory=list)

    # -- verificação estrutural -------------------------------------------

    def violacoes(self, atributos: list[str]) -> list[str]:
        raizes = {a: raiz_do_atributo(a) for a in atributos}
        return [a for a, r in raizes.items() if r in self.componentes_do_rotulo]

    def filtrar(self, atributos: list[str]) -> list[str]:
        """Remove os atributos circulares e registra o que foi removido."""
        maus = self.violacoes(atributos)
        self._violacoes = maus
        if maus:
            diagnostico.registrar(
                area=AREA,
                item=(
                    f"{len(maus)} atributo(s) sao componentes algebricos do rotulo "
                    f"'{self.nome_do_rotulo}' e foram removidos: {sorted(maus)[:12]}"
                ),
                impacto=(
                    "Mantidos, produziriam metrica quase perfeita sem conteudo preditivo: "
                    "o modelo apenas reconstruiria a formula do rotulo. Removidos, as "
                    "metricas caem — e essa queda e o resultado honesto."
                ),
                acao=(
                    "Ao reportar no TCC, apresentar as duas versoes lado a lado (com e "
                    "sem os componentes) e explicitar que a versao 'com' e o limite "
                    "superior artificial. Area: vazamento.GuardaCircularidade."
                ),
                severidade=diagnostico.Severidade.OBSERVA,
            )
        return [a for a in atributos if a not in set(maus)]

    def exigir_limpo(self, atributos: list[str]) -> None:
        maus = self.violacoes(atributos)
        if maus:
            raise VazamentoDetectado(
                f"Atributos circulares em relacao a '{self.nome_do_rotulo}': {maus}. "
                "Use .filtrar() ou redefina o rotulo."
            )

    # -- verificação empírica ---------------------------------------------

    def auditar_correlacao(self, X: pd.DataFrame, y: np.ndarray) -> pd.DataFrame:
        """Procura vazamento que a checagem estrutural não pega.

        Um atributo pode não ser componente declarado do rótulo e ainda assim
        ser função quase determinística dele (ex.: recomputado por outra via).
        Correlação de Spearman perto de 1 é o sintoma.
        """
        y = np.asarray(y, dtype=float)
        linhas = []
        for c in X.columns:
            v = X[c].to_numpy(dtype=float)
            m = np.isfinite(v) & np.isfinite(y)
            if m.sum() < 10 or np.std(v[m]) == 0:
                rho = np.nan
            else:
                rho = float(pd.Series(v[m]).corr(pd.Series(y[m]), method="spearman"))
            linhas.append({"atributo": c, "spearman_com_rotulo": rho,
                           "suspeito": bool(abs(rho) >= self.tolerancia_correlacao)
                           if np.isfinite(rho) else False})
        tabela = pd.DataFrame(linhas).sort_values(
            "spearman_com_rotulo", key=lambda s: s.abs(), ascending=False, ignore_index=True
        )
        suspeitos = tabela.loc[tabela["suspeito"], "atributo"].tolist()
        if suspeitos:
            diagnostico.registrar(
                area=AREA,
                item=(
                    f"Atributo(s) com correlacao de posto >= {self.tolerancia_correlacao} "
                    f"com o rotulo: {suspeitos[:10]}"
                ),
                impacto=(
                    "Indica vazamento nao declarado. Qualquer metrica obtida com esses "
                    "atributos e um limite superior artificial e nao deve ser lida como "
                    "capacidade de deteccao."
                ),
                acao=(
                    "Investigar a origem contabil de cada atributo listado e remove-lo "
                    "ou justificar a manutencao. Area: vazamento.auditar_correlacao()."
                ),
                severidade=diagnostico.Severidade.BLOQUEIA,
            )
        return tabela


# ---------------------------------------------------------------------------
# Vazamento temporal
# ---------------------------------------------------------------------------

def auditar_particao_temporal(df: pd.DataFrame, treino: np.ndarray,
                              teste: np.ndarray) -> dict:
    """Verifica se a partição respeita a ordem do tempo.

    Divisão aleatória 70/30 sobre painel — como no desenho de referência —
    coloca trimestres futuros da mesma instituição no treino e trimestres
    passados no teste. Como indicadores contábeis são altamente persistentes
    dentro da instituição, isso infla a métrica sem que nada tenha sido
    aprendido sobre generalização.
    """
    p_tr = df.loc[treino, "anomes"]
    p_te = df.loc[teste, "anomes"]
    resultado = {
        "max_treino": int(p_tr.max()) if len(p_tr) else None,
        "min_teste": int(p_te.min()) if len(p_te) else None,
        "sobreposicao_temporal": bool(len(p_tr) and len(p_te) and p_tr.max() >= p_te.min()),
        "instituicoes_em_ambos": int(
            len(set(df.loc[treino, "cod_inst"]) & set(df.loc[teste, "cod_inst"]))
        ),
    }
    if resultado["sobreposicao_temporal"]:
        diagnostico.registrar(
            area=AREA,
            item="Ha sobreposicao temporal entre treino e teste.",
            impacto=(
                "Metricas fora da amostra ficam otimistas. Em painel contabil, a "
                "persistencia dentro da instituicao faz o modelo 'reconhecer' a "
                "instituicao em vez de generalizar."
            ),
            acao=(
                "Usar corte estritamente cronologico (ConfigAvaliacao.corte_treino) e, "
                "como robustez, um segundo desenho com particao por instituicao "
                "(GroupKFold). Area: vazamento.auditar_particao_temporal()."
            ),
            severidade=diagnostico.Severidade.BLOQUEIA,
        )
    return resultado


def comparar_desenhos(metricas_temporal: dict, metricas_aleatoria: dict) -> pd.DataFrame:
    """Tabela comparando partição cronológica x aleatória.

    Serve como evidência direta no TCC: a diferença entre as duas colunas
    quantifica quanto da performance reportada em desenhos aleatórios vem de
    vazamento temporal, e não de capacidade preditiva.
    """
    chaves = sorted(set(metricas_temporal) | set(metricas_aleatoria))
    return pd.DataFrame(
        {
            "metrica": chaves,
            "particao_cronologica": [metricas_temporal.get(k) for k in chaves],
            "particao_aleatoria": [metricas_aleatoria.get(k) for k in chaves],
            "diferenca": [
                (metricas_aleatoria.get(k) - metricas_temporal.get(k))
                if isinstance(metricas_aleatoria.get(k), (int, float))
                and isinstance(metricas_temporal.get(k), (int, float))
                else None
                for k in chaves
            ],
        }
    )
