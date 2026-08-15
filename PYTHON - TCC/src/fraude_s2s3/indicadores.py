"""Indicadores de risco de manipulação adaptados a instituições financeiras.

Motivação
---------
Os modelos de referência foram calibrados em empresas **não financeiras**:

* Beneish (1999) — M-Score: DSRI, GMI, AQI, SGI, DEPI, SGAI, LEVI, TATA.
* Dechow et al. (2011) — F-Score/DF-Score: RSST_ACC, CH_REC, CH_INV,
  SOFT_ASSETS, CH_CS, CH_CM, CH_ROA, CH_FCF.
* Piotroski (2000) — PF-Score: nove sinais binários de rentabilidade,
  alavancagem/liquidez e eficiência operacional.

Em banco, parte desses componentes é **inaplicável por construção**: não há
estoque, não há custo das mercadorias vendidas, "vendas" não é receita
operacional no mesmo sentido, e depreciação é irrelevante frente ao balanço.
Aplicá-los sem adaptação produz número — não produz medida.

O que este módulo faz
---------------------
Reconstrói cada componente por **analogia funcional**, preservando a
*intenção econômica* do indicador original e trocando a conta pelo equivalente
bancário. Cada indicador declara explicitamente:

``origem``      de que modelo/componente ele deriva;
``adaptacao``   qual substituição foi feita e por quê;
``leitura``     em que direção o valor sugere risco.

Classificação de evidência (usada no TCC para separar o que é literatura do
que é proposta do autor):

``LIT``   componente com correspondência direta na literatura citada;
``ADAP``  componente da literatura com substituição de conta para banco;
``PROP``  indicador sem correspondente nos modelos originais, proposto a
          partir do arcabouço prudencial (Res. CMN 2.682/1999, Basileia).
          **Requer validação com o orientador**: não é achado consolidado.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import diagnostico

AREA = "indicadores/adaptacao"

EPS = 1e-9


@dataclass(frozen=True)
class Indicador:
    chave: str
    origem: str
    evidencia: str          # LIT | ADAP | PROP
    adaptacao: str
    leitura: str
    requisitos: tuple[str, ...]


CATALOGO: tuple[Indicador, ...] = (
    # ------------------- Analogias aos componentes de Dechow ---------------
    Indicador(
        "soft_assets", "Dechow et al. (2011) — SOFT_ASSETS", "ADAP",
        "Ativos 'moles' = Ativo total menos disponibilidades e menos imobilizado. "
        "Conceito transporta bem para banco: mede a fracao do ativo cuja "
        "mensuracao depende de estimativa e julgamento.",
        "Quanto maior, maior a discricionariedade contabil disponivel.",
        ("ativo_total",),
    ),
    Indicador(
        "delta_carteira", "Dechow et al. (2011) — CH_REC", "ADAP",
        "Recebiveis em banco = carteira de credito. Variacao da carteira sobre "
        "ativo medio.",
        "Crescimento acelerado da carteira sem provisao correspondente e sinal de risco.",
        ("carteira_credito", "ativo_total"),
    ),
    Indicador(
        "delta_tvm", "Dechow et al. (2011) — CH_INV", "ADAP",
        "Nao existe estoque em banco. Substituido por titulos e valores "
        "mobiliarios, que cumprem funcao analoga de ativo de giro sujeito a "
        "mensuracao por valor justo.",
        "Variacao brusca pode indicar reclassificacao entre categorias de TVM.",
        ("tvm", "ativo_total"),
    ),
    Indicador(
        "delta_roa", "Dechow et al. (2011) — CH_ROA", "LIT",
        "Aplicavel sem alteracao.",
        "Queda de ROA aumenta a pressao por manipulacao (elemento 'pressao' do "
        "triangulo da fraude).",
        ("lucro_liquido", "ativo_total"),
    ),
    Indicador(
        "accrual_bancario", "Dechow et al. (2011) — RSST_ACC / Beneish — TATA", "ADAP",
        "Accrual total aproximado pela diferenca entre resultado e um proxy de "
        "geracao de caixa. Sem DFC no IF.data, usa-se: (lucro liquido + despesa "
        "de provisao - variacao de creditos operacionais) / ativo medio.",
        "Accrual alto e persistente indica resultado sustentado por competencia, "
        "nao por caixa.",
        ("lucro_liquido", "ativo_total"),
    ),
    Indicador(
        "delta_capital", "Dechow et al. (2011) / Piotroski — EQ_OFFER", "ADAP",
        "Indicador binario de aumento de capital social no trimestre.",
        "Emissao de capital coincide com periodos de incentivo a reportar bem.",
        ("capital_social",),
    ),

    # ------------------ Analogias aos componentes de Beneish ---------------
    Indicador(
        "gmi_bancario", "Beneish (1999) — GMI", "ADAP",
        "Margem bruta substituida pela margem financeira: resultado bruto da "
        "intermediacao sobre ativo rentavel medio (NIM). GMI = NIM(t-1)/NIM(t).",
        "GMI > 1 indica deterioracao de margem — pressao por compensar no resultado.",
        ("resultado_intermediacao", "ativo_total"),
    ),
    Indicador(
        "sgi_bancario", "Beneish (1999) — SGI", "ADAP",
        "Crescimento de vendas substituido por crescimento da carteira de credito.",
        "Crescimento acelerado e o preditor isolado mais recorrente em episodios de "
        "quebra bancaria; tambem e o instrumento GROWTH usado em Benyasrisawat e "
        "Ounlert (2026).",
        ("carteira_credito",),
    ),
    Indicador(
        "aqi_bancario", "Beneish (1999) — AQI", "ADAP",
        "Qualidade do ativo = participacao de ativos de realizacao incerta "
        "(outros creditos + intangivel + creditos tributarios) no ativo total.",
        "Elevacao indica migracao do balanco para ativos de mensuracao frouxa.",
        ("ativo_total",),
    ),
    Indicador(
        "levi_bancario", "Beneish (1999) — LEVI", "ADAP",
        "Alavancagem contabil (ativo/PL). Complementada, quando disponivel, pelo "
        "indice de Basileia, que e a medida prudencial pertinente.",
        "Alavancagem crescente com Basileia caindo em direcao ao minimo regulatorio "
        "e a configuracao de maior pressao.",
        ("ativo_total", "patrimonio_liquido"),
    ),
    Indicador(
        "sgai_bancario", "Beneish (1999) — SGAI", "ADAP",
        "Indice de eficiencia: despesas administrativas sobre receitas operacionais.",
        "Deterioracao da eficiencia aumenta pressao sobre o resultado.",
        ("despesa_administrativa", "resultado_intermediacao"),
    ),

    # ------------- Indicadores prudenciais propostos (banco) ---------------
    Indicador(
        "cobertura_provisao", "Proposto — Res. CMN 2.682/1999", "PROP",
        "Saldo de provisao sobre carteira classificada em niveis E-H. Mede "
        "suficiencia da provisao frente ao risco ja reconhecido.",
        "Queda da cobertura com carteira E-H estavel ou crescente e o padrao "
        "esperado de subprovisionamento.",
        ("provisao_pcld", "carteira_eh"),
    ),
    Indicador(
        "intensidade_provisao", "Proposto — Res. CMN 2.682/1999", "PROP",
        "Despesa de provisao do periodo sobre carteira media.",
        "Reducao abrupta sem melhora de inadimplencia sugere resultado inflado por "
        "reversao ou nao constituicao de provisao.",
        ("provisao_pcld", "carteira_credito"),
    ),
    Indicador(
        "descasamento_provisao_inad", "Proposto — supervisao prudencial", "PROP",
        "Divergencia entre a variacao da inadimplencia e a variacao da despesa de "
        "provisao (residuo padronizado da relacao entre as duas).",
        "Inadimplencia subindo e provisao nao acompanhando e o descasamento de maior "
        "interesse para o auditor.",
        ("provisao_pcld", "carteira_credito"),
    ),
    Indicador(
        "peso_credito_tributario", "Proposto — qualidade de capital", "PROP",
        "Creditos tributarios sobre patrimonio liquido.",
        "Capital sustentado por ativo fiscal diferido depende de lucro futuro; peso "
        "alto e sinal de fragilidade de capital.",
        ("creditos_tributarios", "patrimonio_liquido"),
    ),
    Indicador(
        "folga_basileia", "Proposto — arcabouco de Basileia (BCB)", "PROP",
        "Distancia do indice de Basileia ao minimo regulatorio aplicavel.",
        "Folga pequena e persistente cria incentivo direto a gerenciar o RWA ou o "
        "resultado.",
        ("indice_basileia",),
    ),
    Indicador(
        "dependencia_nao_recorrente", "Proposto — qualidade do resultado", "PROP",
        "Peso de 'outras receitas operacionais' no resultado total.",
        "Resultado concentrado em linha residual e sinal classico de nao recorrencia.",
        ("outras_receitas_op", "lucro_liquido"),
    ),
)

CATALOGO_POR_CHAVE = {i.chave: i for i in CATALOGO}


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------

def _razao(num: pd.Series, den: pd.Series) -> pd.Series:
    """Divisão protegida: denominador nulo ou negativo vira ausente.

    Denominador negativo em banco (PL negativo, por exemplo) inverte o sinal do
    indicador e produziria leitura invertida — preferimos ausente a errado.
    """
    den = den.where(den.abs() > EPS)
    r = num / den
    return r.replace([np.inf, -np.inf], np.nan)


def _delta(df: pd.DataFrame, coluna: str, grupo: str = "cod_inst", passos: int = 4) -> pd.Series:
    """Variação em relação a ``passos`` trimestres atrás (4 = interanual).

    Comparação interanual, não trimestre contra trimestre: o balanço bancário
    tem sazonalidade (dezembro concentra baixas e constituições) e a diferença
    trimestral confundiria sazonalidade com anomalia.
    """
    if coluna not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df.groupby(grupo, sort=False)[coluna].diff(passos)


def _defasagem(df: pd.DataFrame, coluna: str, grupo: str = "cod_inst", passos: int = 4) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df.groupby(grupo, sort=False)[coluna].shift(passos)


def _tem(df: pd.DataFrame, *cols: str) -> bool:
    return all(c in df.columns and df[c].notna().any() for c in cols)


def construir(df: pd.DataFrame) -> pd.DataFrame:
    """Constrói os indicadores a partir do painel de conceitos contábeis.

    Espera ``df`` ordenado por (cod_inst, anomes) com colunas nomeadas segundo
    :mod:`fraude_s2s3.mapeamento`. Indicadores sem insumo são omitidos e
    reportados como ponto de correção — nunca preenchidos com zero.
    """
    df = df.sort_values(["cod_inst", "anomes"]).reset_index(drop=True)
    out = df[["cod_inst", "anomes"]].copy()
    if "segmento" in df.columns:
        out["segmento"] = df["segmento"].values

    ativo = df.get("ativo_total")
    ativo_medio = None
    if ativo is not None:
        ativo_medio = (ativo + df.groupby("cod_inst", sort=False)["ativo_total"].shift(4)) / 2
        ativo_medio = ativo_medio.fillna(ativo)

    construidos: list[str] = []
    nao_construidos: list[tuple[str, str]] = []

    def registrar(chave: str, serie: pd.Series | None, motivo: str = "") -> None:
        if serie is None:
            nao_construidos.append((chave, motivo))
            return
        out[chave] = serie.values
        construidos.append(chave)

    # ---------------- Dechow adaptados ------------------------------------
    if _tem(df, "ativo_total"):
        moles = df["ativo_total"].copy()
        for c in ("disponibilidades", "imobilizado"):
            if c in df.columns:
                moles = moles - df[c].fillna(0)
        registrar("soft_assets", _razao(moles, df["ativo_total"]))
    else:
        registrar("soft_assets", None, "ativo_total ausente")

    if _tem(df, "carteira_credito", "ativo_total"):
        registrar("delta_carteira", _razao(_delta(df, "carteira_credito"), ativo_medio))
        registrar(
            "sgi_bancario",
            _razao(df["carteira_credito"], _defasagem(df, "carteira_credito")),
        )
    else:
        registrar("delta_carteira", None, "carteira_credito/ativo_total ausentes")
        registrar("sgi_bancario", None, "carteira_credito ausente")

    if _tem(df, "tvm", "ativo_total"):
        registrar("delta_tvm", _razao(_delta(df, "tvm"), ativo_medio))
    else:
        registrar("delta_tvm", None, "tvm ausente")

    if _tem(df, "lucro_liquido", "ativo_total"):
        roa = _razao(df["lucro_liquido"], ativo_medio)
        out["roa"] = roa.values
        registrar("delta_roa", roa - roa.groupby(df["cod_inst"]).shift(4))

        # Accrual bancário: sem DFC no IF.data, o proxy soma de volta a despesa
        # de provisão (item sem efeito caixa no período) e desconta a variação
        # de crédito operacional. É aproximação — está declarada como tal.
        caixa_proxy = df["lucro_liquido"].copy()
        if "despesa_provisao" in df.columns:
            caixa_proxy = caixa_proxy + df["despesa_provisao"].fillna(0).abs()
        if "outros_creditos" in df.columns:
            caixa_proxy = caixa_proxy - _delta(df, "outros_creditos").fillna(0)
        registrar("accrual_bancario", _razao(df["lucro_liquido"] - caixa_proxy, ativo_medio))
    else:
        registrar("delta_roa", None, "lucro_liquido/ativo_total ausentes")
        registrar("accrual_bancario", None, "lucro_liquido/ativo_total ausentes")

    if _tem(df, "capital_social"):
        registrar("delta_capital", (_delta(df, "capital_social") > 0).astype(float))
    else:
        registrar("delta_capital", None, "capital_social ausente")

    # ---------------- Beneish adaptados -----------------------------------
    if _tem(df, "resultado_intermediacao", "ativo_total"):
        nim = _razao(df["resultado_intermediacao"], ativo_medio)
        out["nim"] = nim.values
        nim_ant = nim.groupby(df["cod_inst"]).shift(4)
        registrar("gmi_bancario", _razao(nim_ant, nim))
    else:
        registrar("gmi_bancario", None, "resultado_intermediacao ausente")

    if _tem(df, "ativo_total"):
        opacos = pd.Series(0.0, index=df.index)
        usou = False
        for c in ("outros_creditos", "intangivel", "creditos_tributarios"):
            if c in df.columns:
                opacos = opacos + df[c].fillna(0)
                usou = True
        registrar("aqi_bancario", _razao(opacos, df["ativo_total"]) if usou else None,
                  "nenhum componente de ativo opaco disponivel")
    else:
        registrar("aqi_bancario", None, "ativo_total ausente")

    if _tem(df, "ativo_total", "patrimonio_liquido"):
        registrar("levi_bancario", _razao(df["ativo_total"], df["patrimonio_liquido"]))
    else:
        registrar("levi_bancario", None, "patrimonio_liquido ausente")

    if _tem(df, "despesa_administrativa", "resultado_intermediacao"):
        registrar(
            "sgai_bancario",
            _razao(df["despesa_administrativa"].abs(), df["resultado_intermediacao"].abs()),
        )
    else:
        registrar("sgai_bancario", None, "despesa_administrativa ausente")

    # ---------------- Prudenciais propostos --------------------------------
    if _tem(df, "provisao_pcld", "carteira_eh"):
        registrar("cobertura_provisao", _razao(df["provisao_pcld"].abs(), df["carteira_eh"]))
    else:
        registrar("cobertura_provisao", None, "provisao_pcld/carteira_eh ausentes")

    if _tem(df, "provisao_pcld", "carteira_credito"):
        intensidade = _razao(df["provisao_pcld"].abs(), df["carteira_credito"])
        registrar("intensidade_provisao", intensidade)
        if "inadimplencia" in df.columns:
            d_inad = _delta(df, "inadimplencia")
            d_prov = intensidade - intensidade.groupby(df["cod_inst"]).shift(4)
            registrar("descasamento_provisao_inad", d_inad - d_prov)
        else:
            registrar("descasamento_provisao_inad", None, "inadimplencia ausente")
    else:
        registrar("intensidade_provisao", None, "provisao_pcld/carteira_credito ausentes")
        registrar("descasamento_provisao_inad", None, "provisao_pcld ausente")

    if _tem(df, "creditos_tributarios", "patrimonio_liquido"):
        registrar("peso_credito_tributario",
                  _razao(df["creditos_tributarios"], df["patrimonio_liquido"]))
    else:
        registrar("peso_credito_tributario", None, "creditos_tributarios ausente")

    if _tem(df, "indice_basileia"):
        # PONTO DE ATENCAO: o minimo regulatorio varia no tempo e por
        # instituicao (adicionais de conservacao/contraciclico). Aqui usa-se a
        # distancia a um piso de referencia, e a escolha do piso e registrada.
        piso = 10.5
        registrar("folga_basileia", df["indice_basileia"] - piso)
        diagnostico.registrar(
            area=AREA,
            item=f"Folga de Basileia calculada contra piso fixo de {piso}%.",
            impacto=(
                "O minimo aplicavel varia por instituicao e por data (adicionais de "
                "capital principal). Um piso fixo desloca o indicador para parte da "
                "amostra."
            ),
            acao=(
                "Confirmar o requerimento minimo vigente por trimestre no recorte "
                "2019-2024 e substituir o piso fixo por uma serie de requerimento. "
                "Area: indicadores.construir(), bloco 'folga_basileia'."
            ),
            severidade=diagnostico.Severidade.OBSERVA,
        )
    else:
        registrar("folga_basileia", None, "indice_basileia ausente")

    if _tem(df, "outras_receitas_op", "lucro_liquido"):
        registrar("dependencia_nao_recorrente",
                  _razao(df["outras_receitas_op"].abs(), df["lucro_liquido"].abs()))
    else:
        registrar("dependencia_nao_recorrente", None, "outras_receitas_op ausente")

    if nao_construidos:
        detalhe = "; ".join(f"{k} ({m})" for k, m in nao_construidos)
        propostos = [k for k, _ in nao_construidos
                     if CATALOGO_POR_CHAVE.get(k, None) and CATALOGO_POR_CHAVE[k].evidencia == "PROP"]
        diagnostico.registrar(
            area=AREA,
            item=f"{len(nao_construidos)} indicador(es) nao puderam ser construidos: {detalhe}",
            impacto=(
                "O espaco de atributos efetivo e menor que o descrito na metodologia. "
                + (
                    "Entre os ausentes ha indicadores prudenciais propostos "
                    f"({propostos}), justamente os que diferenciam esta pesquisa da "
                    "aplicacao direta de modelos de empresa nao financeira."
                    if propostos else ""
                )
            ),
            acao=(
                "Ampliar a coleta com os relatorios do IF.data que contem os conceitos "
                "faltantes, ou remover formalmente o indicador da metodologia (secao "
                "3.2.2) para que texto e codigo descrevam a mesma coisa."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )

    out.attrs["indicadores_construidos"] = construidos
    out.attrs["indicadores_ausentes"] = [k for k, _ in nao_construidos]
    return out


def catalogo_df() -> pd.DataFrame:
    """Quadro de operacionalização das variáveis, para anexo do TCC."""
    return pd.DataFrame(
        [
            {
                "indicador": i.chave,
                "origem": i.origem,
                "evidencia": i.evidencia,
                "adaptacao_realizada": i.adaptacao,
                "leitura_de_risco": i.leitura,
            }
            for i in CATALOGO
        ]
    )


def alerta_evidencia() -> str:
    """Texto pronto para a seção de limitações do TCC."""
    n_prop = sum(1 for i in CATALOGO if i.evidencia == "PROP")
    n_adap = sum(1 for i in CATALOGO if i.evidencia == "ADAP")
    n_lit = sum(1 for i in CATALOGO if i.evidencia == "LIT")
    return (
        f"Dos {len(CATALOGO)} indicadores, {n_lit} tem correspondencia direta na "
        f"literatura citada, {n_adap} sao adaptacoes de componentes existentes para "
        f"o balanco bancario e {n_prop} sao proposicoes do autor derivadas do "
        "arcabouco prudencial. Os indicadores da terceira categoria nao possuem "
        "validacao empirica previa e devem ser tratados como contribuicao "
        "exploratoria, sujeita a critica da banca."
    )
