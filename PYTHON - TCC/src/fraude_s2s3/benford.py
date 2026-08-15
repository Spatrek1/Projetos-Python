"""Testes de conformidade a Benford sobre saldos COSIF.

Por que entra no trabalho
-------------------------
A rede neural e os modelos de escore são todos derivados do **mesmo** conjunto
de indicadores. Se todos apontarem a mesma instituição, isso não é
corroboração — é a mesma medida contada três vezes. A lei de Newcomb–Benford
opera sobre outra coisa: a distribuição dos **dígitos** dos saldos publicados,
independentemente de qualquer razão contábil construída aqui.

Referências: Benford (1938); Hill (1995) para a base probabilística; Nigrini
(2012) para a aplicação forense e para os limiares de MAD (desvio absoluto
médio) usados abaixo.

Limitações que precisam constar no TCC
--------------------------------------
1. Saldos COSIF agregados por relatório do IF.data já são somas de contas
   analíticas; a conformidade a Benford é mais fraca em agregados do que em
   lançamentos individuais.
2. Contas com piso, teto ou valor regulado (capital mínimo, índices) violam a
   premissa de escala livre e devem ser excluídas.
3. Desvio de Benford **não é indício de fraude**; é indício de que a série
   não se comporta como número contábil de formação livre. Arredondamento,
   conversão de moeda e reclassificação produzem o mesmo sintoma.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import diagnostico

AREA = "triangulacao/benford"

#: Frequências esperadas do primeiro dígito significativo.
ESPERADO_D1 = np.array([np.log10(1 + 1 / d) for d in range(1, 10)])

#: Frequências esperadas do segundo dígito significativo.
ESPERADO_D2 = np.array(
    [sum(np.log10(1 + 1 / (10 * k + d)) for k in range(1, 10)) for d in range(0, 10)]
)

#: Limiares de conformidade por MAD (Nigrini, 2012), primeiro dígito.
LIMIARES_MAD_D1 = (
    (0.000, 0.006, "conformidade proxima"),
    (0.006, 0.012, "conformidade aceitavel"),
    (0.012, 0.015, "conformidade marginal"),
    (0.015, np.inf, "nao conforme"),
)


def _digitos(valores: np.ndarray, posicao: int) -> np.ndarray:
    """Extrai o dígito significativo na posição indicada (1 = primeiro)."""
    v = np.abs(np.asarray(valores, dtype=float))
    v = v[np.isfinite(v) & (v > 0)]
    if v.size == 0:
        return np.array([], dtype=int)
    escala = 10 ** (np.floor(np.log10(v)))
    normalizado = v / escala                      # em [1, 10)
    return np.floor(normalizado * 10 ** (posicao - 1)).astype(int) % (10 if posicao > 1 else 10)


def testar(valores: np.ndarray, posicao: int = 1) -> dict:
    """Aplica o teste de Benford e devolve estatísticas e classificação."""
    d = _digitos(valores, posicao)
    if posicao == 1:
        d = d[(d >= 1) & (d <= 9)]
        esperado, base = ESPERADO_D1, np.arange(1, 10)
    else:
        d = d[(d >= 0) & (d <= 9)]
        esperado, base = ESPERADO_D2, np.arange(0, 10)

    n = d.size
    if n == 0:
        return {"n": 0, "mad": np.nan, "qui2": np.nan, "classificacao": "sem dados"}

    observado = np.array([(d == k).sum() for k in base]) / n
    mad = float(np.mean(np.abs(observado - esperado)))
    qui2 = float(n * np.sum((observado - esperado) ** 2 / esperado))

    classificacao = "n/d"
    if posicao == 1:
        for inf, sup, rotulo in LIMIARES_MAD_D1:
            if inf <= mad < sup:
                classificacao = rotulo
                break

    return {
        "n": int(n),
        "mad": mad,
        "qui2": qui2,
        "gl": len(base) - 1,
        "classificacao": classificacao,
        "observado": observado,
        "esperado": esperado,
        "digitos": base,
    }


def por_instituicao(painel_longo: pd.DataFrame, coluna_valor: str = "saldo",
                    minimo_observacoes: int = 300) -> pd.DataFrame:
    """Roda o teste separadamente para cada instituição.

    ``minimo_observacoes``: com menos de algumas centenas de saldos o MAD é
    instável e a classificação de Nigrini não se sustenta. Instituições abaixo
    do mínimo são reportadas, não classificadas.
    """
    linhas, poucas = [], []
    for cod, g in painel_longo.groupby("cod_inst", sort=False):
        v = g[coluna_valor].to_numpy(dtype=float)
        r1 = testar(v, 1)
        r2 = testar(v, 2)
        if r1["n"] < minimo_observacoes:
            poucas.append(str(cod))
        linhas.append(
            {
                "cod_inst": cod,
                "n_saldos": r1["n"],
                "mad_d1": r1["mad"],
                "qui2_d1": r1["qui2"],
                "classificacao_d1": r1["classificacao"] if r1["n"] >= minimo_observacoes else "amostra insuficiente",
                "mad_d2": r2["mad"],
                "qui2_d2": r2["qui2"],
            }
        )

    if poucas:
        diagnostico.registrar(
            area=AREA,
            item=f"{len(poucas)} instituicao(oes) com menos de {minimo_observacoes} saldos.",
            impacto=(
                "O MAD dessas instituicoes nao e interpretavel pelos limiares de Nigrini. "
                "Reportar classificacao para elas seria leitura indevida do teste."
            ),
            acao=(
                "Ampliar a granularidade da coleta (mais relatorios COSIF por trimestre) "
                "ou restringir a triangulacao por Benford as instituicoes com massa "
                f"suficiente. Afetadas: {poucas[:8]}. Area: benford.por_instituicao()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )

    diagnostico.registrar(
        area=AREA,
        item="Teste de Benford aplicado sobre saldos agregados de relatorios do IF.data.",
        impacto=(
            "Agregados tem conformidade a Benford mais fraca que lancamentos "
            "individuais. Desvio observado nao autoriza inferencia sobre manipulacao."
        ),
        acao=(
            "No texto do TCC, apresentar Benford como triangulacao independente e "
            "explicitamente NAO como teste de fraude. Se possivel, discutir com o "
            "orientador o acesso a dados mais granulares. Area: benford."
        ),
        severidade=diagnostico.Severidade.OBSERVA,
    )
    return pd.DataFrame(linhas).sort_values("mad_d1", ascending=False, ignore_index=True)
