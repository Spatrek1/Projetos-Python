"""Indicadores de risco de manipulação adaptados a instituições financeiras.

Motivação
---------
Os modelos de referência foram calibrados em empresas **não financeiras**:

* Beneish (1999) — M-Score: DSRI, GMI, AQI, SGI, DEPI, SGAI, LEVI, TATA.
* Dechow et al. (2011) — F-Score: RSST_ACC, CH_REC, CH_INV, SOFT_ASSETS,
  CH_CS, CH_CM, CH_ROA, CH_FCF.
* Piotroski (2000) — PF-Score: nove sinais binários.

Em banco, parte desses componentes é **inaplicável por construção**: não há
estoque, não há custo das mercadorias vendidas, "vendas" não é receita
operacional no mesmo sentido, e depreciação é irrelevante frente ao balanço.

Este módulo reconstrói cada componente por **analogia funcional** — preserva a
intenção econômica do indicador e troca a conta pelo equivalente bancário — e
acrescenta indicadores derivados do arcabouço prudencial.

Classificação de evidência
--------------------------
``LIT``   componente com correspondência direta na literatura citada;
``ADAP``  componente da literatura com substituição de conta para banco;
``PROP``  indicador sem correspondente nos modelos originais, proposto a
          partir do arcabouço prudencial (Res. CMN 2.682/1999, Basileia).
          **Sem validação empírica prévia**; contribuição exploratória.

Convenção de sinais do IF.data
------------------------------
Provisões e despesas são publicadas com **sinal negativo**, de modo que as
identidades contábeis se fecham por soma. Verificado nos arquivos::

    Operações de Crédito (d1)  741.455.019
    Provisão sobre Op. Crédito  -48.436.033
    Operações Líquidas (d)      693.018.986   = soma exata

Os indicadores que exigem magnitude aplicam valor absoluto de forma explícita,
e cada fórmula abaixo indica quando isso ocorre.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import diagnostico
from .config import (PISO_BASILEIA_COOPERATIVA, PISO_BASILEIA_GERAL,
                     TCB_COOPERATIVAS)

AREA = "indicadores/adaptacao"

EPS = 1e-9


@dataclass(frozen=True)
class Indicador:
    chave: str
    origem: str
    evidencia: str          # LIT | ADAP | PROP
    formula: str
    adaptacao: str
    leitura: str
    requisitos: tuple[str, ...]


CATALOGO: tuple[Indicador, ...] = (
    # ------------------- Analogias a Dechow et al. (2011) ------------------
    Indicador(
        "soft_assets", "Dechow et al. (2011) — SOFT_ASSETS", "ADAP",
        "(Ativo total − Disponibilidades − Permanente) / Ativo total",
        "Conceito transporta bem para banco: mede a fracao do ativo cuja "
        "mensuracao depende de estimativa e julgamento. 'Disponibilidades' soma "
        "caixa e aplicacoes interfinanceiras de liquidez.",
        "Quanto maior, maior a discricionariedade contabil disponivel.",
        ("ativo_total",),
    ),
    Indicador(
        "delta_carteira", "Dechow et al. (2011) — CH_REC", "ADAP",
        "Δ₄(Carteira de crédito) / Ativo médio",
        "Recebiveis em banco correspondem a carteira de credito bruta, antes "
        "da provisao.",
        "Crescimento acelerado sem provisao correspondente e sinal de risco.",
        ("carteira_credito", "ativo_total"),
    ),
    Indicador(
        "peso_carteira", "Condicao de escopo (proposto)", "PROP",
        "Carteira de crédito / Ativo total",
        "Nao e indicador de manipulacao, e condicao de materialidade. Distingue "
        "instituicao de varejo de banco de atacado e de investimento, distincao "
        "que a segmentacao S1-S5 da Res. CMN 4.553/2017 nao captura: ela ordena "
        "por porte e relevancia sistemica, nao por modelo de negocio.",
        "Abaixo de 10% o credito e parcela imaterial do balanco e as razoes "
        "construidas sobre a carteira deixam de ser comparaveis as dos pares.",
        ("carteira_credito", "ativo_total"),
    ),
    Indicador(
        "delta_tvm", "Dechow et al. (2011) — CH_INV", "ADAP",
        "Δ₄(TVM) / Ativo médio",
        "Nao existe estoque em banco. Substituido por titulos e valores "
        "mobiliarios, ativo de giro sujeito a mensuracao por valor justo.",
        "Variacao brusca pode indicar reclassificacao entre categorias de TVM.",
        ("tvm", "ativo_total"),
    ),
    Indicador(
        "delta_roa", "Dechow et al. (2011) — CH_ROA", "LIT",
        "ROA(t) − ROA(t−4), com ROA = Lucro líquido / Ativo médio",
        "Aplicavel sem alteracao.",
        "Queda de ROA aumenta a pressao por manipulacao (elemento 'pressao' do "
        "triangulo da fraude).",
        ("lucro_liquido", "ativo_total"),
    ),
    Indicador(
        "accrual_bancario", "Dechow et al. (2011) — RSST_ACC / Beneish — TATA", "ADAP",
        "(Lucro líquido − proxy de caixa) / Ativo médio, com proxy de caixa = "
        "Lucro líquido + |Despesa de provisão| − Δ₄(Outros créditos)",
        "O IF.data nao publica demonstracao dos fluxos de caixa. O proxy soma "
        "de volta a despesa de provisao — item sem efeito caixa no periodo — e "
        "desconta a variacao de creditos operacionais. E APROXIMACAO DECLARADA.",
        "Accrual alto e persistente indica resultado sustentado por competencia, "
        "nao por caixa.",
        ("lucro_liquido", "ativo_total"),
    ),

    # ------------------ Analogias a Beneish (1999) -------------------------
    Indicador(
        "gmi_bancario", "Beneish (1999) — GMI", "ADAP",
        "NIM(t−4) / NIM(t), com NIM = Resultado de intermediação / Ativo médio",
        "Margem bruta substituida pela margem financeira liquida (NIM), que "
        "cumpre a mesma funcao economica em banco.",
        "GMI > 1 indica deterioracao de margem — pressao por compensar no resultado.",
        ("resultado_intermediacao", "ativo_total"),
    ),
    Indicador(
        "sgi_bancario", "Beneish (1999) — SGI", "ADAP",
        "Carteira de crédito(t) / Carteira de crédito(t−4)",
        "Crescimento de vendas substituido por crescimento da carteira de credito.",
        "Crescimento acelerado e o preditor isolado mais recorrente em episodios "
        "de quebra bancaria; e tambem o instrumento GROWTH de Benyasrisawat e "
        "Ounlert (2026).",
        ("carteira_credito",),
    ),
    Indicador(
        "aqi_bancario", "Beneish (1999) — AQI", "ADAP",
        "(Outros créditos + Permanente) / Ativo total",
        "Qualidade do ativo medida pela participacao de ativos de realizacao "
        "incerta. O IF.data nao separa intangivel nem creditos tributarios: "
        "ambos estao dentro de 'Permanente Ajustado'.",
        "Elevacao indica migracao do balanco para ativos de mensuracao frouxa.",
        ("ativo_total",),
    ),
    Indicador(
        "levi_bancario", "Beneish (1999) — LEVI", "ADAP",
        "Ativo total / Patrimônio líquido",
        "Alavancagem contabil. Complementada pelo indice de Basileia, que e a "
        "medida prudencial pertinente.",
        "Alavancagem crescente com Basileia caindo e a configuracao de maior pressao.",
        ("ativo_total", "patrimonio_liquido"),
    ),
    Indicador(
        "sgai_bancario", "Beneish (1999) — SGAI", "ADAP",
        "(|Despesa de pessoal| + |Despesa administrativa|) / "
        "(Resultado de intermediação + Receita de serviços)",
        "Indice de eficiencia operacional bancaria. Despesas vem com sinal "
        "negativo no IF.data; aplica-se valor absoluto.",
        "Deterioracao da eficiencia aumenta pressao sobre o resultado.",
        ("despesa_administrativa", "resultado_intermediacao"),
    ),

    # ---------------- Prudenciais propostos (Res. 2.682, Basileia) ---------
    Indicador(
        "cobertura_provisao", "Proposto — Res. CMN 2.682/1999", "PROP",
        "|Provisão sobre operações de crédito| / Carteira de crédito bruta",
        "O IF.data nao publica a carteira por nivel de risco (AA-H) nos "
        "relatorios do recorte. A cobertura e medida sobre a carteira bruta, "
        "nao sobre a carteira E-H. E medida menos sensivel: capta o nivel de "
        "provisionamento, nao sua suficiencia frente ao risco ja reconhecido.",
        "Queda da cobertura sem melhora correspondente de qualidade da carteira "
        "e o padrao esperado de subprovisionamento.",
        ("provisao_pcld", "carteira_credito"),
    ),
    Indicador(
        "intensidade_despesa_provisao", "Proposto — Res. CMN 2.682/1999", "PROP",
        "|Despesa de provisão do período| / Carteira média",
        "Fluxo, nao estoque: mede quanto foi constituido no trimestre. "
        "Complementa a cobertura, que e saldo acumulado.",
        "Reducao abrupta sem melhora de qualidade sugere resultado inflado por "
        "nao constituicao ou reversao de provisao.",
        ("despesa_provisao", "carteira_credito"),
    ),
    Indicador(
        "descasamento_provisao", "Proposto — supervisão prudencial", "PROP",
        "Δ₄(Cobertura de provisão) − Δ₄(Carteira/Ativo)",
        "Divergencia entre a evolucao do provisionamento e a da exposicao a "
        "credito. Substitui o descasamento provisao x inadimplencia, "
        "inviavel por ausencia do indice de inadimplencia no IF.data.",
        "Carteira crescendo com cobertura caindo e o descasamento de maior "
        "interesse para o auditor.",
        ("provisao_pcld", "carteira_credito", "ativo_total"),
    ),
    Indicador(
        "folga_basileia", "Proposto — arcabouço de Basileia (BCB)", "PROP",
        "Índice de Basileia − piso aplicável, com piso de 10,5 p.p. para "
        "instituições sob regime pleno e faixa de 13 a 18 p.p. para "
        "cooperativas de crédito (TCB b3S e b3C)",
        "O requerimento de cooperativas situa-se em faixa, nao em valor unico, e "
        "o IF.data nao publica o enquadramento que define a posicao exata. A "
        "folga principal e medida contra o limite INFERIOR da faixa; a variante "
        "'folga_basileia_conservadora' usa o limite superior, e "
        "'basileia_zona_incerta' marca as observacoes em que a conclusao muda "
        "conforme o piso adotado.",
        "Folga pequena e persistente cria incentivo direto a gerenciar o RWA ou "
        "o resultado.",
        ("indice_basileia",),
    ),
    Indicador(
        "folga_basileia_conservadora", "Proposto — arcabouço de Basileia (BCB)", "PROP",
        "Índice de Basileia − limite SUPERIOR do piso aplicável (18 p.p. para "
        "cooperativas; 10,5 p.p. para as demais)",
        "Cenario conservador da folga de capital, para as cooperativas cujo "
        "requerimento exato dentro da faixa nao e publicado.",
        "Folga negativa aqui e positiva em 'folga_basileia' delimita a zona de "
        "incerteza regulatoria.",
        ("indice_basileia",),
    ),
    Indicador(
        "basileia_zona_incerta", "Proposto — arcabouço de Basileia (BCB)", "PROP",
        "1 se cooperativa com Índice de Basileia entre 13 e 18 p.p.; 0 caso contrário",
        "Marcador das observacoes em que a conclusao sobre conformidade de "
        "capital depende de qual ponto da faixa se adota.",
        "Nao e indicador de risco: e sinalizador de incerteza de mensuracao, e "
        "deve ser lido como tal.",
        ("indice_basileia",),
    ),
    Indicador(
        "qualidade_capital", "Proposto — arcabouço de Basileia (BCB)", "PROP",
        "Capital principal / Patrimônio de referência",
        "Fracao do capital regulatorio composta por capital principal, de "
        "maior capacidade de absorcao de perdas.",
        "Queda indica capital sustentado por instrumentos de qualidade inferior.",
        ("capital_principal", "patrimonio_referencia"),
    ),
    Indicador(
        "dependencia_nao_recorrente", "Proposto — qualidade do resultado", "PROP",
        "|Resultado não operacional| / |Resultado antes da tributação|",
        "Peso do resultado nao operacional na formacao do lucro.",
        "Resultado concentrado em linha nao recorrente e sinal classico de "
        "qualidade baixa de lucro.",
        ("resultado_nao_operacional", "resultado_antes_trib"),
    ),
    Indicador(
        "carga_tributaria_efetiva", "Proposto — qualidade do resultado", "PROP",
        "|IR e CSLL| / |Resultado antes da tributação|",
        "Carga efetiva sobre o resultado. Sem correspondente nos modelos de "
        "origem, mas classica em analise forense: divergencia persistente entre "
        "carga efetiva e nominal sinaliza diferencas entre lucro contabil e "
        "fiscal.",
        "Carga muito abaixo da nominal, de forma persistente, merece exame.",
        ("ir_csll", "resultado_antes_trib"),
    ),
    Indicador(
        "concentracao_captacao", "Proposto — risco de liquidez", "PROP",
        "Depósitos a prazo / Captações totais",
        "Composicao da captacao. Deposito a prazo e a fonte mais sensivel a "
        "percepcao de risco pelo mercado.",
        "Concentracao elevada aumenta a vulnerabilidade a corrida de saques.",
        ("depositos_prazo", "captacoes"),
    ),
    Indicador(
        "discrepancia_carteira", "Proposto — consistência entre relatórios", "PROP",
        "(Carteira classificada − Carteira contábil) / Carteira contábil",
        "O IF.data publica a carteira em dois relatorios com definicoes "
        "distintas: 'Carteira de Credito Classificada' no Resumo e 'Operacoes "
        "de Credito' no Ativo. A divergencia entre elas e informacao, nao ruido.",
        "Divergencia atipica entre as duas medidas sugere diferenca entre o "
        "que foi classificado para fins de risco e o que foi registrado "
        "contabilmente.",
        ("carteira_classificada", "carteira_credito"),
    ),
)

CATALOGO_POR_CHAVE = {i.chave: i for i in CATALOGO}


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------

def _razao(num: pd.Series, den: pd.Series) -> pd.Series:
    """Divisão protegida: denominador nulo ou muito próximo de zero vira ausente."""
    den = den.where(den.abs() > EPS)
    return (num / den).replace([np.inf, -np.inf], np.nan)


def _delta(df: pd.DataFrame, coluna: str, passos: int = 4) -> pd.Series:
    """Variação em relação a ``passos`` trimestres atrás (4 = interanual).

    Comparação interanual, não trimestre contra trimestre: o balanço bancário
    tem sazonalidade — dezembro concentra baixas e constituições — e a
    diferença trimestral confundiria sazonalidade com anomalia.
    """
    if coluna not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df.groupby("cod_inst", sort=False)[coluna].diff(passos)


def _defasagem(df: pd.DataFrame, coluna: str, passos: int = 4) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df.groupby("cod_inst", sort=False)[coluna].shift(passos)


def _tem(df: pd.DataFrame, *cols: str) -> bool:
    return all(c in df.columns and df[c].notna().any() for c in cols)


def construir(df: pd.DataFrame,
              piso_geral: float = PISO_BASILEIA_GERAL,
              faixa_cooperativa: tuple[float, float] = PISO_BASILEIA_COOPERATIVA,
              ) -> pd.DataFrame:
    """Constrói os indicadores a partir do painel de conceitos contábeis.

    Espera ``df`` com colunas nomeadas segundo :mod:`fraude_s2s3.consolidacao`.
    Indicador sem insumo é **omitido e reportado** — nunca preenchido com zero.
    """
    df = df.sort_values(["cod_inst", "anomes"]).reset_index(drop=True)
    out = df[[c for c in ("cod_inst", "anomes", "segmento", "Instituição", "TCB", "SR")
              if c in df.columns]].copy()

    ativo = df.get("ativo_total")
    ativo_medio = None
    if ativo is not None:
        anterior = df.groupby("cod_inst", sort=False)["ativo_total"].shift(4)
        ativo_medio = ((ativo + anterior) / 2).fillna(ativo)

    construidos: list[str] = []
    nao_construidos: list[tuple[str, str]] = []

    def registrar(chave: str, serie: pd.Series | None, motivo: str = "") -> None:
        if serie is None:
            nao_construidos.append((chave, motivo))
            return
        out[chave] = serie.values
        construidos.append(chave)

    # ------------------------- Dechow adaptados ---------------------------
    if _tem(df, "ativo_total"):
        moles = df["ativo_total"].copy()
        for c in ("disponibilidades", "permanente"):
            if c in df.columns:
                moles = moles - df[c].fillna(0)
        registrar("soft_assets", _razao(moles, df["ativo_total"]))
    else:
        registrar("soft_assets", None, "ativo_total ausente")

    if _tem(df, "carteira_credito", "ativo_total"):
        registrar("delta_carteira", _razao(_delta(df, "carteira_credito"), ativo_medio))
        registrar("sgi_bancario", _razao(df["carteira_credito"], _defasagem(df, "carteira_credito")))
        # Participacao do credito no ativo. Serve de condicao de escopo: onde o
        # credito e parcela imaterial do balanco, as razoes construidas sobre a
        # carteira (cobertura de provisao, crescimento) nao sao economicamente
        # comparaveis as de uma instituicao de varejo.
        registrar("peso_carteira", _razao(df["carteira_credito"], df["ativo_total"]))
    else:
        registrar("delta_carteira", None, "carteira_credito ausente")
        registrar("sgi_bancario", None, "carteira_credito ausente")
        registrar("peso_carteira", None, "carteira_credito ausente")

    if _tem(df, "tvm", "ativo_total"):
        registrar("delta_tvm", _razao(_delta(df, "tvm"), ativo_medio))
    else:
        registrar("delta_tvm", None, "tvm ausente")

    if _tem(df, "lucro_liquido", "ativo_total"):
        roa = _razao(df["lucro_liquido"], ativo_medio)
        out["roa"] = roa.values
        registrar("delta_roa", roa - roa.groupby(df["cod_inst"]).shift(4))

        caixa = df["lucro_liquido"].copy()
        if "despesa_provisao" in df.columns:
            caixa = caixa + df["despesa_provisao"].abs().fillna(0)
        if "outros_creditos" in df.columns:
            caixa = caixa - _delta(df, "outros_creditos").fillna(0)
        registrar("accrual_bancario", _razao(df["lucro_liquido"] - caixa, ativo_medio))
    else:
        registrar("delta_roa", None, "lucro_liquido ausente")
        registrar("accrual_bancario", None, "lucro_liquido ausente")

    # ------------------------- Beneish adaptados --------------------------
    if _tem(df, "resultado_intermediacao", "ativo_total"):
        nim = _razao(df["resultado_intermediacao"], ativo_medio)
        out["nim"] = nim.values
        registrar("gmi_bancario", _razao(nim.groupby(df["cod_inst"]).shift(4), nim))
    else:
        registrar("gmi_bancario", None, "resultado_intermediacao ausente")

    if _tem(df, "ativo_total"):
        opacos, usou = pd.Series(0.0, index=df.index), False
        for c in ("outros_creditos", "permanente"):
            if c in df.columns:
                opacos, usou = opacos + df[c].fillna(0), True
        registrar("aqi_bancario", _razao(opacos, df["ativo_total"]) if usou else None,
                  "componentes de ativo opaco ausentes")
    else:
        registrar("aqi_bancario", None, "ativo_total ausente")

    if _tem(df, "ativo_total", "patrimonio_liquido"):
        registrar("levi_bancario", _razao(df["ativo_total"], df["patrimonio_liquido"]))
    else:
        registrar("levi_bancario", None, "patrimonio_liquido ausente")

    if _tem(df, "despesa_administrativa", "resultado_intermediacao"):
        despesas = df["despesa_administrativa"].abs().fillna(0)
        if "despesa_pessoal" in df.columns:
            despesas = despesas + df["despesa_pessoal"].abs().fillna(0)
        receitas = df["resultado_intermediacao"].copy()
        if "receita_servicos" in df.columns:
            receitas = receitas + df["receita_servicos"].fillna(0)
        registrar("sgai_bancario", _razao(despesas, receitas))
    else:
        registrar("sgai_bancario", None, "despesa_administrativa ausente")

    # --------------------- Prudenciais propostos --------------------------
    if _tem(df, "provisao_pcld", "carteira_credito"):
        cobertura = _razao(df["provisao_pcld"].abs(), df["carteira_credito"])
        registrar("cobertura_provisao", cobertura)
        if _tem(df, "ativo_total"):
            peso = _razao(df["carteira_credito"], df["ativo_total"])
            d_cob = cobertura - cobertura.groupby(df["cod_inst"]).shift(4)
            d_peso = peso - peso.groupby(df["cod_inst"]).shift(4)
            registrar("descasamento_provisao", d_cob - d_peso)
        else:
            registrar("descasamento_provisao", None, "ativo_total ausente")
    else:
        registrar("cobertura_provisao", None, "provisao_pcld/carteira_credito ausentes")
        registrar("descasamento_provisao", None, "provisao_pcld ausente")

    if _tem(df, "despesa_provisao", "carteira_credito"):
        carteira_media = ((df["carteira_credito"] + _defasagem(df, "carteira_credito")) / 2
                          ).fillna(df["carteira_credito"])
        registrar("intensidade_despesa_provisao",
                  _razao(df["despesa_provisao"].abs(), carteira_media))
    else:
        registrar("intensidade_despesa_provisao", None, "despesa_provisao ausente")

    if _tem(df, "indice_basileia"):
        piso_min, piso_max = faixa_cooperativa
        e_coop = (df["TCB"].isin(TCB_COOPERATIVAS) if "TCB" in df.columns
                  else pd.Series(False, index=df.index))

        piso_aplicavel = pd.Series(piso_geral, index=df.index, dtype=float)
        piso_aplicavel[e_coop] = piso_min
        piso_conservador = pd.Series(piso_geral, index=df.index, dtype=float)
        piso_conservador[e_coop] = piso_max

        out["piso_basileia_aplicado"] = piso_aplicavel.values
        registrar("folga_basileia", df["indice_basileia"] - piso_aplicavel)
        registrar("folga_basileia_conservadora", df["indice_basileia"] - piso_conservador)

        # Observações em que a conformidade depende de qual ponto da faixa vale.
        incerta = (e_coop
                   & df["indice_basileia"].ge(piso_min)
                   & df["indice_basileia"].lt(piso_max))
        registrar("basileia_zona_incerta", incerta.astype(float))

        n_coop = int(e_coop.sum())
        n_incerta = int(incerta.sum())
        diagnostico.registrar(
            area=AREA,
            item=(
                f"Folga de Basileia: piso de {piso_geral} p.p. para instituicoes sob "
                f"regime pleno e faixa de {piso_min}-{piso_max} p.p. para as "
                f"{n_coop} observacao(oes) de cooperativas (TCB {list(TCB_COOPERATIVAS)}). "
                f"{n_incerta} observacao(oes) caem dentro da faixa."
            ),
            impacto=(
                "Para as observacoes dentro da faixa, a conclusao sobre folga de capital "
                "muda conforme o piso adotado: sao positivas contra o limite inferior e "
                "negativas contra o superior. A coluna 'basileia_zona_incerta' as marca."
                if n_incerta else
                "Nenhuma observacao caiu dentro da faixa; a escolha do ponto da faixa nao "
                "altera o sinal da folga nesta amostra."
            ),
            acao=(
                "Confirmar o requerimento efetivamente aplicavel a cada cooperativa da "
                "amostra — depende do enquadramento em regime prudencial simplificado, "
                "informacao que o IF.data nao publica nos relatorios do recorte. Enquanto "
                "nao confirmado, reportar a folga com a ressalva da faixa. "
                "Area: indicadores.construir(), bloco 'folga_basileia'; parametros em "
                "config.PISO_BASILEIA_GERAL e config.PISO_BASILEIA_COOPERATIVA."
            ),
            severidade=(diagnostico.Severidade.COMPROMETE if n_incerta
                        else diagnostico.Severidade.OBSERVA),
        )
    else:
        registrar("folga_basileia", None, "indice_basileia ausente")
        registrar("folga_basileia_conservadora", None, "indice_basileia ausente")
        registrar("basileia_zona_incerta", None, "indice_basileia ausente")

    if _tem(df, "capital_principal", "patrimonio_referencia"):
        registrar("qualidade_capital",
                  _razao(df["capital_principal"], df["patrimonio_referencia"]))
    else:
        registrar("qualidade_capital", None, "capital_principal ausente")

    if _tem(df, "resultado_nao_operacional", "resultado_antes_trib"):
        registrar("dependencia_nao_recorrente",
                  _razao(df["resultado_nao_operacional"].abs(),
                         df["resultado_antes_trib"].abs()))
    else:
        registrar("dependencia_nao_recorrente", None, "resultado_nao_operacional ausente")

    if _tem(df, "ir_csll", "resultado_antes_trib"):
        registrar("carga_tributaria_efetiva",
                  _razao(df["ir_csll"].abs(), df["resultado_antes_trib"].abs()))
    else:
        registrar("carga_tributaria_efetiva", None, "ir_csll ausente")

    if _tem(df, "depositos_prazo", "captacoes"):
        registrar("concentracao_captacao", _razao(df["depositos_prazo"], df["captacoes"]))
    else:
        registrar("concentracao_captacao", None, "depositos_prazo ausente")

    if _tem(df, "carteira_classificada", "carteira_credito"):
        registrar("discrepancia_carteira",
                  _razao(df["carteira_classificada"] - df["carteira_credito"],
                         df["carteira_credito"]))
    else:
        registrar("discrepancia_carteira", None, "carteira_classificada ausente")

    if nao_construidos:
        detalhe = "; ".join(f"{k} ({m})" for k, m in nao_construidos)
        propostos = [k for k, _ in nao_construidos
                     if CATALOGO_POR_CHAVE.get(k) and CATALOGO_POR_CHAVE[k].evidencia == "PROP"]
        diagnostico.registrar(
            area=AREA,
            item=f"{len(nao_construidos)} indicador(es) nao construidos: {detalhe}",
            impacto=(
                "O espaco de atributos efetivo e menor que o descrito na metodologia."
                + (f" Entre os ausentes ha indicadores prudenciais propostos ({propostos}), "
                   "que sao justamente os que diferenciam esta pesquisa da aplicacao "
                   "direta de modelos de empresa nao financeira." if propostos else "")
            ),
            acao=(
                "Ampliar a coleta com os relatorios que contem os conceitos faltantes, ou "
                "remover formalmente o indicador da metodologia para que texto e codigo "
                "descrevam a mesma coisa. Area: indicadores.construir()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )

    out.attrs["indicadores_construidos"] = construidos
    out.attrs["indicadores_ausentes"] = [k for k, _ in nao_construidos]
    return out


def catalogo_df() -> pd.DataFrame:
    """Quadro de operacionalização das variáveis, para anexo do TCC."""
    return pd.DataFrame([
        {"indicador": i.chave, "origem": i.origem, "evidencia": i.evidencia,
         "formula": i.formula, "adaptacao_realizada": i.adaptacao,
         "leitura_de_risco": i.leitura}
        for i in CATALOGO
    ])


def alerta_evidencia() -> str:
    """Texto pronto para a seção de limitações do TCC."""
    n = {c: sum(1 for i in CATALOGO if i.evidencia == c) for c in ("LIT", "ADAP", "PROP")}
    return (
        f"Dos {len(CATALOGO)} indicadores, {n['LIT']} tem correspondencia direta na "
        f"literatura citada, {n['ADAP']} sao adaptacoes de componentes existentes para o "
        f"balanco bancario e {n['PROP']} sao proposicoes do autor derivadas do arcabouco "
        "prudencial. Os indicadores da terceira categoria nao possuem validacao empirica "
        "previa e devem ser tratados como contribuicao exploratoria, sujeita a critica "
        "da banca."
    )
