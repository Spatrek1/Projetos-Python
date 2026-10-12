"""Construção do painel de atributos para os modelos.

Decisões que este módulo materializa (todas discutíveis, todas explícitas):

1. **Winsorização por trimestre**, não global. Contas COSIF mudam de escala ao
   longo de 2019–2024; cortar caudas contra a distribuição do próprio trimestre
   preserva a comparação transversal.
2. **Z-score dentro de (segmento, trimestre)**. A pergunta do estudo é
   "esta instituição destoa dos seus pares agora?", não "destoa da população
   inteira de 2019 a 2024". Sem esse passo, o modelo aprende principalmente
   *tamanho* e *ciclo econômico*.
3. **Normalização ajustada só no treino**. Os parâmetros de escala vêm da
   janela de treino e são aplicados a validação e teste. O contrário é
   vazamento — e é o erro mais comum em replicações deste tipo de trabalho.
4. **Ausentes marcados, não imputados por média**. Cada atributo ganha uma
   coluna-sombra ``faltante_<x>``; a média imputada entraria como "valor
   típico" e reduziria artificialmente o erro de reconstrução da rede.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import diagnostico
from .config import CONFIG, ConfigPainel

AREA = "painel/tratamento"

CHAVES = ("cod_inst", "anomes", "segmento")


@dataclass
class Escalador:
    """Normalização ajustada no treino e reaplicada nos demais recortes."""

    metodo: str = "rank_gauss"
    _quantis: dict[str, np.ndarray] = field(default_factory=dict)
    _medias: dict[str, float] = field(default_factory=dict)
    _desvios: dict[str, float] = field(default_factory=dict)
    colunas: list[str] = field(default_factory=list)

    def ajustar(self, df: pd.DataFrame, colunas: list[str]) -> "Escalador":
        self.colunas = list(colunas)
        for c in self.colunas:
            v = df[c].dropna().to_numpy(dtype=float)
            if v.size == 0:
                self._medias[c], self._desvios[c] = 0.0, 1.0
                continue
            if self.metodo == "rank_gauss":
                self._quantis[c] = np.quantile(v, np.linspace(0, 1, 1001))
            self._medias[c] = float(np.mean(v))
            self._desvios[c] = float(np.std(v)) or 1.0
        return self

    def transformar(self, df: pd.DataFrame) -> pd.DataFrame:
        saida = df.copy()
        for c in self.colunas:
            v = saida[c].to_numpy(dtype=float)
            if self.metodo == "rank_gauss" and c in self._quantis:
                q = self._quantis[c]
                # posição do valor na distribuição de treino -> uniforme -> gauss
                pos = np.searchsorted(q, v) / (len(q) - 1)
                pos = np.clip(pos, 1e-4, 1 - 1e-4)
                z = _probit(pos)
            else:
                z = (v - self._medias[c]) / self._desvios[c]
            z[np.isnan(v)] = np.nan
            saida[c] = z
        return saida


def _probit(p: np.ndarray) -> np.ndarray:
    """Inversa da normal padrão (Acklam), sem dependência de SciPy."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    x = np.empty_like(p)

    m = p < plow
    if m.any():
        q = np.sqrt(-2 * np.log(p[m]))
        x[m] = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    m = p > phigh
    if m.any():
        q = np.sqrt(-2 * np.log(1 - p[m]))
        x[m] = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    m = (p >= plow) & (p <= phigh)
    if m.any():
        q = p[m] - 0.5
        r = q * q
        x[m] = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    return x


# ---------------------------------------------------------------------------

def winsorizar(df: pd.DataFrame, colunas: list[str], cfg: ConfigPainel) -> pd.DataFrame:
    """Corta caudas dentro de cada trimestre."""
    saida = df.copy()
    for c in colunas:
        saida[c] = (
            saida.groupby("anomes")[c]
            .transform(lambda s: s.clip(s.quantile(cfg.winsor_inferior),
                                        s.quantile(cfg.winsor_superior)))
        )
    return saida


def z_por_pares(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Padroniza cada indicador dentro de (segmento, trimestre).

    Mediana e MAD em vez de média e desvio: com dezenas de instituições e
    caudas pesadas, a média é puxada pelo próprio caso extremo que se quer
    detectar.
    """
    saida = df.copy()
    novas = []
    for c in colunas:
        g = saida.groupby(["segmento", "anomes"])[c]
        mediana = g.transform("median")
        mad = g.transform(lambda s: (s - s.median()).abs().median())
        escala = (mad * 1.4826).replace(0, np.nan)
        nome = f"z_par_{c}"
        saida[nome] = (saida[c] - mediana) / escala
        novas.append(nome)
    saida.attrs["colunas_z_par"] = novas
    return saida


def descartar_esparsos(df: pd.DataFrame, colunas: list[str], cfg: ConfigPainel) -> list[str]:
    """Remove indicadores com ausência acima do tolerado."""
    manter, descartados = [], []
    for c in colunas:
        frac = float(df[c].isna().mean())
        (manter if frac <= cfg.max_ausentes_indicador else descartados).append(
            c if frac <= cfg.max_ausentes_indicador else (c, round(frac, 3))
        )
    if descartados:
        diagnostico.registrar(
            area=AREA,
            item=f"Indicadores descartados por ausencia excessiva: {descartados}",
            impacto=(
                "Reduz a dimensao do espaco de atributos. Se o descarte atingir os "
                "indicadores prudenciais propostos, o modelo volta a ser, na pratica, "
                "uma aplicacao de modelo de empresa nao financeira."
            ),
            acao=(
                f"Ou ampliar a coleta para cobrir esses conceitos, ou elevar "
                f"ConfigPainel.max_ausentes_indicador (hoje {cfg.max_ausentes_indicador}) "
                "assumindo mais ausencia. Area: painel.descartar_esparsos()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
    return manter


def marcar_ausentes(df: pd.DataFrame, colunas: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Cria colunas-sombra de ausência e zera o valor faltante após normalizar.

    Zero, depois da normalização, é a posição central da distribuição: o
    equivalente a "sem informação" em vez de "valor extremo".
    """
    saida = df.copy()
    sombras = []
    for c in colunas:
        nome = f"faltante_{c}"
        saida[nome] = saida[c].isna().astype(float)
        sombras.append(nome)
    saida[colunas] = saida[colunas].fillna(0.0)
    return saida, sombras


def filtrar_historico(df: pd.DataFrame, cfg: ConfigPainel) -> pd.DataFrame:
    """Exige histórico mínimo por instituição."""
    n = df.groupby("cod_inst")["anomes"].nunique()
    curtos = n[n < cfg.min_trimestres_instituicao].index.tolist()
    if curtos:
        diagnostico.registrar(
            area=AREA,
            item=f"{len(curtos)} instituicao(oes) com menos de {cfg.min_trimestres_instituicao} trimestres.",
            impacto=(
                "Instituicoes recem-autorizadas ou incorporadas ficam de fora. Isso "
                "introduz vies de sobrevivencia: instituicoes que deixaram de operar "
                "no periodo — exatamente as de maior interesse forense — sao as mais "
                "propensas a ter historico curto."
            ),
            acao=(
                "Verificar caso a caso se a instituicao saiu por incorporacao, "
                "liquidacao ou cancelamento de autorizacao, e reportar essa lista "
                "no TCC como parte da descricao da amostra. Area: painel.filtrar_historico()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
    return df[~df["cod_inst"].isin(curtos)].copy()


@dataclass
class PainelPronto:
    dados: pd.DataFrame
    atributos: list[str]
    escalador: Escalador
    treino: np.ndarray
    validacao: np.ndarray
    teste: np.ndarray

    def matriz(self, mascara: np.ndarray) -> np.ndarray:
        return self.dados.loc[mascara, self.atributos].to_numpy(dtype=np.float32)

    def resumo(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"recorte": "treino", "n": int(self.treino.sum()),
                 "instituicoes": self.dados.loc[self.treino, "cod_inst"].nunique()},
                {"recorte": "validacao", "n": int(self.validacao.sum()),
                 "instituicoes": self.dados.loc[self.validacao, "cod_inst"].nunique()},
                {"recorte": "teste", "n": int(self.teste.sum()),
                 "instituicoes": self.dados.loc[self.teste, "cod_inst"].nunique()},
            ]
        )


def construir(indicadores: pd.DataFrame, cfg=None) -> PainelPronto:
    """Pipeline completo de tratamento até a matriz de entrada da rede."""
    cfg_painel = (cfg or CONFIG).painel
    cfg_aval = (cfg or CONFIG).avaliacao

    df = indicadores.copy()

    # Atributo e coluna numerica que nao seja chave. A selecao e por tipo, e nao
    # por lista de nomes, porque o painel gravado em dados/tratados carrega
    # tambem identificacao textual — Instituicao, TCB, SR — e um painel lido de
    # CSV perde o .attrs que diria quais colunas sao indicadores. Sem isso, um
    # rotulo de instituicao entraria no espaco de atributos da rede.
    candidatos = [c for c in df.columns if c not in CHAVES]
    brutos = [c for c in candidatos
              if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])]
    descartados = [c for c in candidatos if c not in brutos]
    if descartados:
        diagnostico.registrar(
            area=AREA,
            item=f"Colunas nao numericas fora do espaco de atributos: {descartados}",
            impacto=("Sao identificacao, nao medida. Permanecem no painel para leitura "
                     "e rastreabilidade, mas nao entram na matriz da rede."),
            acao=("Nenhuma, se forem mesmo identificacao. Se algum indicador numerico "
                  "caiu aqui, ele foi lido como texto — conferir o CSV de origem. "
                  "Area: painel.construir()."),
            severidade=diagnostico.Severidade.OBSERVA,
        )

    df = filtrar_historico(df, cfg_painel)
    brutos = descartar_esparsos(df, brutos, cfg_painel)
    if not brutos:
        diagnostico.registrar(
            area=AREA,
            item="Nenhum indicador sobreviveu ao filtro de ausencia.",
            impacto="Nao ha espaco de atributos; a rede nao pode ser treinada.",
            acao="Revisar a coleta e o mapeamento contabil. Area: painel.construir().",
            severidade=diagnostico.Severidade.BLOQUEIA,
        )
        raise ValueError("Painel vazio: ver pontos de correcao.")

    df = winsorizar(df, brutos, cfg_painel)
    if cfg_painel.z_score_por_pares:
        df = z_por_pares(df, brutos)
        atributos = brutos + list(df.attrs.get("colunas_z_par", []))
    else:
        atributos = list(brutos)

    treino = (df["anomes"] <= cfg_aval.corte_treino).to_numpy()
    validacao = ((df["anomes"] > cfg_aval.corte_treino) &
                 (df["anomes"] <= cfg_aval.corte_validacao)).to_numpy()
    teste = (df["anomes"] > cfg_aval.corte_validacao).to_numpy()

    for nome, m in (("treino", treino), ("validacao", validacao), ("teste", teste)):
        if m.sum() == 0:
            diagnostico.registrar(
                area=AREA,
                item=f"Recorte temporal '{nome}' ficou vazio.",
                impacto="A avaliacao fora da amostra nao pode ser executada.",
                acao=(
                    "Ajustar ConfigAvaliacao.corte_treino / corte_validacao ao periodo "
                    "efetivamente coletado. Area: painel.construir()."
                ),
                severidade=diagnostico.Severidade.BLOQUEIA,
            )

    escalador = Escalador(cfg_painel.normalizacao).ajustar(df.loc[treino], atributos)
    df = escalador.transformar(df)
    df, sombras = marcar_ausentes(df, atributos)

    return PainelPronto(
        dados=df, atributos=atributos + sombras, escalador=escalador,
        treino=treino, validacao=validacao, teste=teste,
    )


def sequencias(painel: PainelPronto, janela: int | None = None
               ) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Empilha janelas temporais por instituição para os modelos sequenciais.

    Devolve ``(X, y, indice)`` em que ``X`` tem forma (n, janela, atributos),
    ``y`` é o vetor do trimestre seguinte (alvo de previsão) e ``indice``
    identifica (cod_inst, anomes) do alvo.
    """
    janela = janela or CONFIG.painel.janela_temporal
    df = painel.dados.sort_values(["cod_inst", "anomes"])
    xs, ys, idx = [], [], []
    for cod, g in df.groupby("cod_inst", sort=False):
        m = g[painel.atributos].to_numpy(dtype=np.float32)
        periodos_ = g["anomes"].to_numpy()
        for i in range(janela, len(g)):
            xs.append(m[i - janela:i])
            ys.append(m[i])
            idx.append((cod, periodos_[i]))
    if not xs:
        diagnostico.registrar(
            area=AREA,
            item=f"Nenhuma sequencia de {janela} trimestres pode ser formada.",
            impacto="O modelo sequencial (quebra estrutural) nao pode ser treinado.",
            acao=(
                f"Reduzir ConfigPainel.janela_temporal (hoje {janela}) ou revisar a "
                "continuidade do painel. Area: painel.sequencias()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
        vazio = np.empty((0, janela, len(painel.atributos)), dtype=np.float32)
        return vazio, np.empty((0, len(painel.atributos)), dtype=np.float32), pd.DataFrame(
            columns=["cod_inst", "anomes"]
        )
    return (
        np.stack(xs), np.stack(ys),
        pd.DataFrame(idx, columns=["cod_inst", "anomes"]),
    )
