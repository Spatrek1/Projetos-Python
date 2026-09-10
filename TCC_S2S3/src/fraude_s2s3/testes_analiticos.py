"""Testes analíticos substantivos sobre os seis parâmetros contábeis obrigatórios.

O que são
---------
Procedimentos analíticos no sentido da auditoria: comparações entre valores
registrados e expectativas construídas a partir dos pares e do próprio
histórico da instituição. Cada teste isola **um mecanismo de manipulação
conhecido** e produz uma afirmação verificável.

Diferença em relação à rede neural
----------------------------------
A rede produz um escore agregado — "esta instituição-trimestre destoa" — e a
decomposição diz em quais variáveis. Os testes aqui fazem o caminho inverso:
partem de uma hipótese contábil específica e a testam diretamente.

Servem a três propósitos:

1. **Referência interpretável** para confrontar com o escore da rede. Se a
   rede sinaliza onde nenhum teste sinaliza, é preciso explicar o quê ela viu.
2. **Ponte com a prática de auditoria**, que trabalha com procedimentos
   nomeados, não com escores.
3. **Resultado independente de treino** — não dependem de partição, semente
   nem convergência, e por isso são reprodutíveis por qualquer terceiro.

Ancoragem nos parâmetros obrigatórios
-------------------------------------
=========================  ==========================================
Parâmetro                  Teste
=========================  ==========================================
``provisao_pcld``          T1 — Suficiência de provisão
``carteira_credito``       T2 — Crescimento da carteira
``ativo_total``            T3 — Composição e opacidade do ativo
``patrimonio_liquido``     T4 — Alavancagem e adequação de capital
``resultado_intermediacao``T5 — Margem financeira
``lucro_liquido``          T6 — Qualidade do resultado
=========================  ==========================================

Advertência que acompanha toda saída
------------------------------------
Sinalização **não** é indício de irregularidade. É divergência em relação ao
comportamento dos pares, que constitui hipótese a ser examinada por
procedimento de auditoria. Explicações legítimas — mudança de modelo de
negócio, incorporação, alteração de política contábil — produzem o mesmo
sintoma.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import diagnostico

AREA = "testes_analiticos"

#: Limiar padrão em desvios (MAD) para sinalizar divergência frente aos pares.
#:
#: Sob normalidade, 2,5 desvios corresponderiam a cerca de 1% da distribuição
#: em cada cauda. **Essa proporção não se verifica nesta base**: os indicadores
#: são razões contábeis de cauda pesada e, em vários deles, concentradas em
#: zero, de modo que o MAD é pequeno frente à cauda. A taxa observada por teste
#: fica entre 3% e 25% conforme o limiar (ver :func:`sensibilidade`).
#:
#: O limiar é, portanto, um parâmetro de calibração da carga de exame, não um
#: nível de significância. O TCC deve reportar o valor adotado, a taxa de
#: sinalização resultante e a tabela de sensibilidade.
LIMIAR_PADRAO = 2.5

#: Fração do limiar exigida da medida principal quando há condição corroborante.
#: Mantém as condições secundárias atreladas ao limiar declarado — sem isso a
#: taxa de sinalização fica insensível ao parâmetro e a análise de
#: sensibilidade perde sentido.
FRACAO_CORROBORACAO = 0.6


@dataclass(frozen=True)
class TesteAnalitico:
    codigo: str
    nome: str
    parametro: str
    hipotese: str
    calculo: str
    sinaliza: str
    procedimento: str
    requisitos: tuple[str, ...]


CATALOGO: tuple[TesteAnalitico, ...] = (
    TesteAnalitico(
        "T1", "Suficiência de provisão (PCLD)", "provisao_pcld",
        "A provisão constituída acompanha a exposição a risco de crédito.",
        "cobertura = |provisao| / carteira de credito bruta. Compara-se o nivel "
        "com os pares do mesmo segmento e trimestre em escala logaritmica, e "
        "confronta-se a variacao interanual da cobertura com a da propria carteira.",
        "Carteira viva com provisao exatamente zero; OU cobertura muito abaixo "
        "da dos pares; OU cobertura ja baixa e em queda enquanto a carteira cresce.",
        "Examinar a classificação de risco da carteira (Res. CMN 2.682/1999), a "
        "política de provisionamento e as reversões do período. Subprovisionar "
        "e o mecanismo mais direto de inflar resultado em instituicao financeira.",
        ("provisao_pcld", "carteira_credito"),
    ),
    TesteAnalitico(
        "T2", "Crescimento da carteira de crédito", "carteira_credito",
        "O crescimento da carteira é compatível com o dos pares e sustentado "
        "por capital e provisionamento correspondentes.",
        "Razão carteira(t)/carteira(t−4) e variação da participação da carteira "
        "no ativo, ambas comparadas aos pares.",
        "Crescimento muito acima dos pares, sobretudo acompanhado de cobertura "
        "de provisão estável ou em queda.",
        "Verificar originação, concentração por tomador e setor, e política de "
        "concessão. Crescimento acelerado e o preditor isolado mais recorrente "
        "em episodios de quebra bancaria.",
        ("carteira_credito", "ativo_total"),
    ),
    TesteAnalitico(
        "T3", "Composição e opacidade do ativo", "ativo_total",
        "A composição do ativo não migra para contas de mensuração discricionária.",
        "soft_assets = (ativo − disponibilidades − permanente) / ativo; e "
        "opacidade = (outros créditos + permanente) / ativo. Nível e variação "
        "interanual, contra os pares.",
        "Elevação atípica da participação de ativos cuja mensuração depende de "
        "estimativa.",
        "Examinar a natureza de 'outros créditos', a realizabilidade dos ativos "
        "de longo prazo e eventuais reclassificacoes entre grupos do balanco.",
        ("ativo_total",),
    ),
    TesteAnalitico(
        "T4", "Alavancagem e adequação de capital", "patrimonio_liquido",
        "A alavancagem é compatível com os pares e a folga de capital "
        "regulatório é adequada.",
        "alavancagem = ativo / patrimônio líquido; folga = índice de Basileia − "
        "piso aplicável. Nível e variação, contra os pares.",
        "Alavancagem acima dos pares combinada com folga de capital reduzida ou "
        "em queda.",
        "Confrontar com o requerimento vigente e os adicionais de capital. "
        "Folga pequena e persistente cria incentivo direto a gerenciar o RWA ou "
        "o resultado.",
        ("ativo_total", "patrimonio_liquido"),
    ),
    TesteAnalitico(
        "T5", "Margem financeira", "resultado_intermediacao",
        "A margem financeira é compatível com a composição da carteira e com os pares.",
        "NIM = resultado de intermediação / ativo médio. Nível e variação "
        "interanual, contra os pares.",
        "NIM muito acima dos pares — que pode indicar reconhecimento antecipado "
        "de receita — ou deterioração abrupta, que aumenta a pressão por "
        "compensar no resultado.",
        "Examinar o reconhecimento de rendas de operações de crédito, a "
        "apropriação de receitas por competência e as operações renegociadas.",
        ("resultado_intermediacao", "ativo_total"),
    ),
    TesteAnalitico(
        "T6", "Qualidade do resultado", "lucro_liquido",
        "O lucro é sustentado por operação recorrente e por geração de caixa.",
        "accrual bancário sobre ativo médio; participação do resultado não "
        "operacional; carga tributária efetiva. Todos contra os pares.",
        "Accrual atipico frente aos pares; ou accrual ja apreciavel corroborado "
        "por dependencia de resultado nao recorrente ou por carga tributaria "
        "efetiva muito distante da nominal.",
        "Examinar a natureza das outras receitas operacionais, os eventos não "
        "recorrentes do periodo e a conciliacao entre lucro contabil e fiscal.",
        ("lucro_liquido", "ativo_total"),
    ),
)

CATALOGO_POR_CODIGO = {t.codigo: t for t in CATALOGO}


# ---------------------------------------------------------------------------

def _z_pares(df: pd.DataFrame, coluna: str) -> pd.Series:
    """Desvios em relação à mediana dos pares, escalados pelo MAD.

    Mediana e MAD em vez de média e desvio: com dezenas de instituições e
    caudas pesadas, a média é puxada pelo próprio caso extremo que se procura.
    O fator 1,4826 torna o MAD comparável ao desvio-padrão sob normalidade.
    """
    if coluna not in df.columns:
        return pd.Series(np.nan, index=df.index)
    g = df.groupby(["segmento", "anomes"])[coluna]
    mediana = g.transform("median")
    mad = g.transform(lambda s: (s - s.median()).abs().median())
    escala = (mad * 1.4826).replace(0, np.nan)
    return (df[coluna] - mediana) / escala


def _z_pares_log(df: pd.DataFrame, coluna: str) -> pd.Series:
    """Desvios frente aos pares na escala logarítmica.

    Para razões estritamente positivas e assimétricas à direita — a cobertura
    de provisão é o caso — o desvio simétrico em MAD é geometricamente errado:
    a variável é limitada em zero à esquerda e ilimitada à direita, de modo que
    a cauda esquerda fica comprimida. Nesta base, cobertura **exatamente zero**
    dista apenas cerca de 2,1 desvios da mediana dos pares, enquanto a cauda
    direita alcança mais de 14. Um limiar simétrico nunca alcançaria a condição
    que o teste existe para detectar.

    Em log, a comparação passa a ser multiplicativa — "um terço da mediana dos
    pares" pesa tanto quanto "o triplo" — que é a leitura correta para uma
    razão. Valores nulos ou negativos ficam ausentes e são tratados à parte.
    """
    if coluna not in df.columns:
        return pd.Series(np.nan, index=df.index)
    positivo = df[coluna].where(df[coluna] > 0)
    aux = df[["segmento", "anomes"]].copy()
    aux["_l"] = np.log(positivo)
    g = aux.groupby(["segmento", "anomes"])["_l"]
    mediana = g.transform("median")
    mad = g.transform(lambda x: (x - x.median()).abs().median())
    escala = (mad * 1.4826).replace(0, np.nan)
    return (aux["_l"] - mediana) / escala


def _escopo_credito(df: pd.DataFrame) -> pd.Series:
    """Onde o crédito é parcela material do ativo — escopo de T1 e T2.

    Fora desse recorte os testes de carteira não se aplicam. Peso ausente é
    tratado como fora de escopo: sem saber a participação do crédito não há
    base para afirmar que a razão é comparável.
    """
    if "peso_carteira" not in df.columns:
        return pd.Series(True, index=df.index)
    return (df["peso_carteira"] >= PESO_MINIMO_CARTEIRA).fillna(False)


def _delta4(df: pd.DataFrame, coluna: str) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df.groupby("cod_inst", sort=False)[coluna].diff(4)


def aplicar(ind: pd.DataFrame, limiar: float = LIMIAR_PADRAO,
            registrar_diagnostico: bool = True) -> pd.DataFrame:
    """Executa os seis testes e devolve o quadro de sinalizações.

    ``ind`` é a saída de :func:`fraude_s2s3.indicadores.construir`, ordenada
    por (cod_inst, anomes) e contendo a coluna ``segmento``.

    Devolve uma linha por (instituição, trimestre) com, para cada teste, o
    desvio medido e a marcação de sinalização.
    """
    df = ind.sort_values(["cod_inst", "anomes"]).reset_index(drop=True).copy()
    out = df[[c for c in ("cod_inst", "anomes", "segmento", "Instituição", "TCB")
              if c in df.columns]].copy()

    # Toda condição corroborante é exigida junto a um desvio já apreciável da
    # medida principal, e esse patamar acompanha o limiar declarado.
    corrob = limiar * FRACAO_CORROBORACAO
    ausentes: list[str] = []
    falso = pd.Series(False, index=df.index)

    # -- T1  Suficiência de provisão ---------------------------------------
    # Duas condições distintas, reportadas separadamente:
    #  (a) carteira viva com provisão registrada como exatamente zero — não é
    #      cauda de distribuição, é condição categórica;
    #  (b) cobertura muito abaixo da dos pares, medida em escala logarítmica
    #      (ver _z_pares_log), com queda da cobertura sob carteira em expansão
    #      como corroboração.
    if {"cobertura_provisao", "delta_carteira"} <= set(df.columns):
        z_cob = _z_pares_log(df, "cobertura_provisao")
        d_cob = _delta4(df, "cobertura_provisao")
        cresce = (df["delta_carteira"] > 0).fillna(False)
        sem_provisao = (df["cobertura_provisao"] == 0).fillna(False)
        no_escopo = _escopo_credito(df)
        out["T1_z_cobertura_log"] = z_cob.values
        out["T1_delta_cobertura"] = d_cob.values
        out["T1_sem_provisao"] = (sem_provisao & no_escopo).values
        out["T1_no_escopo"] = no_escopo.values
        out["T1_sinaliza"] = (
            no_escopo & (
                sem_provisao
                | (z_cob < -limiar).fillna(False)
                | ((z_cob < -corrob).fillna(False) & (d_cob < 0).fillna(False) & cresce)
            )
        ).values
        no_teste = sem_provisao & no_escopo
        if registrar_diagnostico and sem_provisao.any():
            diagnostico.registrar(
                area=AREA,
                item=(f"{int(sem_provisao.sum())} observacoes de "
                      f"{df.loc[sem_provisao, 'cod_inst'].nunique()} instituicoes "
                      "registram carteira de credito com provisao exatamente zero; "
                      f"destas, {int(no_teste.sum())} tem carteira material e sao "
                      "sinalizadas por T1."),
                impacto=("Sao sinalizadas por T1 como condicao categorica, nao por "
                         "limiar. Pode ser carteira integralmente classificada em AA "
                         "(Res. CMN 2.682/1999), que dispensa provisionamento, ou "
                         "falha de preenchimento do informe."),
                acao=("Conferir no IF.data a composicao por nivel de risco dessas "
                      "instituicoes antes de tratar como divergencia. "
                      "Area: testes_analiticos.aplicar(), teste T1."),
                severidade=diagnostico.Severidade.OBSERVA,
            )
    else:
        ausentes.append("T1")

    # -- T2  Crescimento da carteira ---------------------------------------
    # Medida principal: crescimento interanual frente aos pares.
    # Corroboração: cobertura de provisão estável ou em queda.
    if "sgi_bancario" in df.columns:
        z_cre = _z_pares(df, "sgi_bancario")
        out["T2_z_crescimento"] = z_cre.values
        cob_caindo = (_delta4(df, "cobertura_provisao") <= 0).fillna(False) \
            if "cobertura_provisao" in df.columns else falso
        out["T2_sinaliza"] = (
            _escopo_credito(df) & (
                (z_cre > limiar).fillna(False)
                | ((z_cre > corrob).fillna(False) & cob_caindo)
            )
        ).values
    else:
        ausentes.append("T2")

    # -- T3  Composição e opacidade do ativo -------------------------------
    # Medida principal: opacidade frente aos pares.
    # Corroboração: opacidade em elevação no próprio histórico.
    if {"soft_assets", "aqi_bancario"} <= set(df.columns):
        z_soft = _z_pares(df, "soft_assets")
        z_opac = _z_pares(df, "aqi_bancario")
        d_opac = _delta4(df, "aqi_bancario")
        out["T3_z_soft_assets"] = z_soft.values
        out["T3_z_opacidade"] = z_opac.values
        out["T3_sinaliza"] = (
            (z_opac > limiar).fillna(False)
            | ((z_opac > corrob).fillna(False) & (d_opac > 0).fillna(False))
        ).values
    else:
        ausentes.append("T3")

    # -- T4  Alavancagem e capital -----------------------------------------
    # Medida principal: alavancagem frente aos pares.
    # Corroboração: folga de capital abaixo da dos pares.
    # Folga negativa sinaliza por si: é descumprimento do piso, fato objetivo.
    if "levi_bancario" in df.columns:
        z_alav = _z_pares(df, "levi_bancario")
        out["T4_z_alavancagem"] = z_alav.values
        if "folga_basileia" in df.columns:
            z_folga = _z_pares(df, "folga_basileia")
            out["T4_z_folga_capital"] = z_folga.values
            out["T4_sinaliza"] = (
                (df["folga_basileia"] < 0).fillna(False)
                | (z_alav > limiar).fillna(False)
                | ((z_alav > corrob).fillna(False) & (z_folga < -corrob).fillna(False))
            ).values
        else:
            out["T4_sinaliza"] = (z_alav > limiar).fillna(False).values
    else:
        ausentes.append("T4")

    # -- T5  Margem financeira ---------------------------------------------
    # Medida principal: NIM frente aos pares, nas duas caudas.
    # Corroboração: margem em deterioração no próprio histórico.
    if "nim" in df.columns:
        z_nim = _z_pares(df, "nim")
        d_nim = _delta4(df, "nim")
        out["T5_z_margem"] = z_nim.values
        out["T5_sinaliza"] = (
            (z_nim.abs() > limiar).fillna(False)
            | ((z_nim < -corrob).fillna(False) & (d_nim < 0).fillna(False))
        ).values
    else:
        ausentes.append("T5")

    # -- T6  Qualidade do resultado ----------------------------------------
    # Medida principal: accrual bancário — a medida consagrada de qualidade do
    # resultado (Dechow). Dependência de não recorrente e carga tributária
    # efetiva entram como corroboração, não como gatilhos independentes:
    # tomá-las pelo máximo equivale a unir três testes e multiplica a taxa de
    # sinalização sem ganho de conteúdo.
    if "accrual_bancario" in df.columns:
        z_acc = _z_pares(df, "accrual_bancario")
        out["T6_z_accrual"] = z_acc.values
        apoios = []
        for c, rotulo in (("dependencia_nao_recorrente", "T6_z_nao_recorrente"),
                          ("carga_tributaria_efetiva", "T6_z_carga_tributaria")):
            if c in df.columns:
                z = _z_pares(df, c)
                out[rotulo] = z.values
                apoios.append((z.abs() > limiar).fillna(False))
        corroborado = falso
        for a in apoios:
            corroborado = corroborado | a
        out["T6_sinaliza"] = (
            (z_acc.abs() > limiar).fillna(False)
            | ((z_acc.abs() > corrob).fillna(False) & corroborado)
        ).values
    else:
        ausentes.append("T6")

    marcas = [c for c in out.columns if c.endswith("_sinaliza")]
    out["n_testes_sinalizados"] = out[marcas].sum(axis=1).astype(int)
    out["testes_sinalizados"] = out[marcas].apply(
        lambda r: ",".join(c.split("_")[0] for c in marcas if r[c]), axis=1)

    if not registrar_diagnostico:
        return out

    if ausentes:
        diagnostico.registrar(
            area=AREA,
            item=f"Testes nao executados por falta de insumo: {ausentes}",
            impacto="A cobertura dos mecanismos de manipulacao fica incompleta.",
            acao=("Verificar quais indicadores faltam em indicadores.construir(). "
                  "Area: testes_analiticos.aplicar()."),
            severidade=diagnostico.Severidade.COMPROMETE,
        )

    diagnostico.registrar(
        area=AREA,
        item=f"Testes analiticos aplicados com limiar de {limiar} desvios (MAD) frente aos pares.",
        impacto=(
            "Sinalizacao NAO e indicio de irregularidade: e divergencia frente aos "
            "pares, que constitui hipotese a examinar. Mudanca de modelo de negocio, "
            "incorporacao e alteracao de politica contabil produzem o mesmo sintoma."
        ),
        acao=(
            "Ao reportar no TCC, nomear como 'observacoes sinalizadas para exame' e "
            "nunca como 'instituicoes com indicio de fraude'. O limiar e parametro: "
            "reportar o valor adotado e a sensibilidade do resultado a ele. "
            "Area: testes_analiticos.aplicar()."
        ),
        severidade=diagnostico.Severidade.COMPROMETE,
    )
    return out


def resumo(sinal: pd.DataFrame) -> pd.DataFrame:
    """Quantas observações e instituições cada teste sinalizou."""
    linhas = []
    for t in CATALOGO:
        col = f"{t.codigo}_sinaliza"
        if col not in sinal.columns:
            linhas.append({"teste": t.codigo, "nome": t.nome, "parametro": t.parametro,
                           "observacoes": None, "instituicoes": None, "pct": None})
            continue
        m = sinal[col].astype(bool)
        linhas.append({
            "teste": t.codigo, "nome": t.nome, "parametro": t.parametro,
            "observacoes": int(m.sum()),
            "instituicoes": int(sinal.loc[m, "cod_inst"].nunique()),
            "pct": round(float(m.mean()) * 100, 1),
        })
    return pd.DataFrame(linhas)


def catalogo_df() -> pd.DataFrame:
    """Quadro dos testes, para anexo do TCC."""
    return pd.DataFrame([
        {"teste": t.codigo, "nome": t.nome, "parametro_ancora": t.parametro,
         "hipotese": t.hipotese, "calculo": t.calculo,
         "criterio_de_sinalizacao": t.sinaliza,
         "procedimento_de_auditoria": t.procedimento}
        for t in CATALOGO
    ])


def detalhar(sinal: pd.DataFrame, cod_inst: str, anomes: int) -> str:
    """Texto auditável para uma observação específica."""
    linha = sinal[(sinal["cod_inst"].astype(str) == str(cod_inst))
                  & (sinal["anomes"] == anomes)]
    if linha.empty:
        return f"Sem registro para {cod_inst} em {anomes}."
    r = linha.iloc[0]
    nome = r.get("Instituição", cod_inst)
    marcados = [c for c in CATALOGO if r.get(f"{c.codigo}_sinaliza", False)]
    if not marcados:
        return f"{nome} ({anomes}): nenhum teste sinalizado."

    partes = [f"{nome} — {anomes}", "=" * 70]
    for t in marcados:
        partes.append(f"\n[{t.codigo}] {t.nome}")
        partes.append(f"  Hipotese testada : {t.hipotese}")
        partes.append(f"  Criterio         : {t.sinaliza}")
        for c in sinal.columns:
            if c.startswith(f"{t.codigo}_z") and pd.notna(r[c]):
                partes.append(f"  {c:<17}: {r[c]:+.2f} desvios frente aos pares")
        partes.append(f"  Procedimento     : {t.procedimento}")
    partes.append(
        "\nSinalizacao e hipotese para direcionamento de procedimento de auditoria, "
        "nao indicio de irregularidade."
    )
    return "\n".join(partes)


def sensibilidade(ind: pd.DataFrame,
                  limiares: tuple[float, ...] = (2.0, 2.5, 3.0, 3.5, 4.0, 5.0)
                  ) -> pd.DataFrame:
    """Taxa de sinalização de cada teste em função do limiar, em %.

    Tabela obrigatória no relato: o limiar é parâmetro de calibração, e o
    leitor precisa poder julgar quanto do resultado depende dele.
    """
    linhas = []
    for lim in limiares:
        s = aplicar(ind, limiar=lim, registrar_diagnostico=False)
        linha = {"limiar": lim}
        for t in CATALOGO:
            col = f"{t.codigo}_sinaliza"
            linha[t.codigo] = round(float(s[col].mean()) * 100, 1) if col in s else None
        linha["ao_menos_um"] = round(float((s["n_testes_sinalizados"] > 0).mean()) * 100, 1)
        linhas.append(linha)
    return pd.DataFrame(linhas)


#: Fração dos trimestres da instituição a partir da qual a sinalização é
#: tratada como característica estrutural, e não como evento.
CORTE_ESTRUTURAL = 0.60

#: Abaixo desta fração a sinalização é pontual.
CORTE_PONTUAL = 0.15

#: Participação mínima do crédito no ativo para que T1 e T2 se apliquem.
#:
#: Condição de materialidade, não de limiar. Em banco de atacado e de
#: investimento o crédito é parcela residual do balanço — a mediana da amostra
#: fica em torno de 5% do ativo, contra 36% nas demais instituições — e a
#: cobertura de provisão deixa de ser grandeza comparável à de uma instituição
#: de varejo. Sem esse recorte, T1 sinaliza modelo de negócio, não divergência
#: de comportamento contábil.
#:
#: A segmentação S1–S5 não resolve isso: a Res. CMN 4.553/2017 ordena por porte
#: e relevância sistêmica, não por natureza da carteira, de modo que banco de
#: atacado e cooperativa de varejo dividem o mesmo grupo de comparação.
PESO_MINIMO_CARTEIRA = 0.10


def classificar_persistencia(sinal: pd.DataFrame) -> pd.DataFrame:
    """Separa sinalização estrutural de sinalização episódica.

    Por que isso é necessário
    -------------------------
    A comparação com os pares mede **nível**, e nível persistentemente distinto
    reflete o modelo de negócio da instituição, não uma ocorrência. Nesta base o
    efeito é grande: o teste T1 sinaliza sobretudo bancos de atacado e de
    investimento — cuja carteira é corporativa, classificada em níveis de risco
    baixos e por isso pouco provisionada — em todos ou quase todos os seus
    trimestres. Ler isso como divergência seria erro de interpretação: é a
    carteira que é diferente, não o comportamento contábil.

    O procedimento analítico se interessa por **mudança**. Uma instituição que
    destoa em 2 de 24 trimestres oferece uma pergunta datada, que pode ser
    confrontada com fatos do período. Uma que destoa em 24 de 24 oferece apenas
    a constatação de que opera em outro segmento de mercado.

    Devolve uma linha por (instituição, teste) com a fração de trimestres
    sinalizados e a classificação em ``estrutural``, ``intermitente`` ou
    ``pontual``.
    """
    linhas = []
    for t in CATALOGO:
        col = f"{t.codigo}_sinaliza"
        if col not in sinal.columns:
            continue
        g = sinal.groupby("cod_inst")
        for cod, bloco in g:
            n = len(bloco)
            k = int(bloco[col].sum())
            if k == 0:
                continue
            frac = k / n
            classe = ("estrutural" if frac >= CORTE_ESTRUTURAL
                      else "pontual" if frac <= CORTE_PONTUAL
                      else "intermitente")
            linhas.append({
                "cod_inst": cod,
                "Instituição": bloco["Instituição"].iloc[0] if "Instituição" in bloco else "",
                "segmento": bloco["segmento"].iloc[0] if "segmento" in bloco else "",
                "teste": t.codigo,
                "trimestres_sinalizados": k,
                "trimestres_observados": n,
                "fracao": round(frac, 3),
                "classe": classe,
            })
    if not linhas:
        return pd.DataFrame(columns=["cod_inst", "Instituição", "segmento", "teste",
                                     "trimestres_sinalizados", "trimestres_observados",
                                     "fracao", "classe"])
    return (pd.DataFrame(linhas)
            .sort_values(["teste", "fracao"], ascending=[True, False])
            .reset_index(drop=True))


def foco_de_exame(sinal: pd.DataFrame) -> pd.DataFrame:
    """As observações que efetivamente merecem procedimento de auditoria.

    Retém apenas sinalizações **não estruturais** — aquelas em que a
    instituição destoa dos pares em parte de seus trimestres e não em todos.
    É o recorte que se leva para exame documental.
    """
    pers = classificar_persistencia(sinal)
    if pers.empty:
        return sinal.iloc[0:0].copy()
    episodico = {(r.cod_inst, r.teste) for r in pers.itertuples()
                 if r.classe != "estrutural"}

    marcas = [c for c in sinal.columns if c.endswith("_sinaliza")]
    out = sinal.copy()
    for c in marcas:
        codigo = c.split("_")[0]
        manter = out["cod_inst"].map(lambda x, k=codigo: (x, k) in episodico)
        out[c] = out[c].astype(bool) & manter
    out["n_testes_sinalizados"] = out[marcas].sum(axis=1).astype(int)
    out["testes_sinalizados"] = out[marcas].apply(
        lambda r: ",".join(c.split("_")[0] for c in marcas if r[c]), axis=1)
    return out[out["n_testes_sinalizados"] > 0].reset_index(drop=True)
