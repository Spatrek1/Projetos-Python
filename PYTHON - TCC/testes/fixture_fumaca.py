"""ATENÇÃO — ISTO NÃO É DADO. É APARATO DE TESTE.

Gera um painel artificial com a *forma* do painel do IF.data (mesmas colunas,
mesma granularidade trimestral) para verificar se o código executa fim a fim.

Regras de uso, sem exceção:

1. Nenhum número produzido a partir daqui pode aparecer no TCC — nem em
   tabela, nem em gráfico, nem em texto. Não são dados do Banco Central; são
   números pseudoaleatórios.
2. Serve para uma pergunta só: "o pipeline roda sem erro e as peças se
   encaixam?". Não serve para avaliar modelo, comparar arquitetura ou calibrar
   hiperparâmetro.
3. Quando o IF.data estiver acessível, este módulo deixa de ser usado.

O gerador embute algumas instituições com desvio de comportamento apenas para
exercitar os caminhos de código da detecção — o que ele "detecta" é o próprio
desvio que o gerador colocou, e isso não informa nada sobre desempenho real.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

AVISO = (
    "PAINEL ARTIFICIAL — gerado por testes/fixture_fumaca.py apenas para teste "
    "de execucao. NAO utilizar em nenhuma analise do TCC."
)


def painel_artificial(n_instituicoes: int = 40, semente: int = 7) -> pd.DataFrame:
    """Painel sintético com as colunas de conceito esperadas pelo pipeline."""
    rng = np.random.default_rng(semente)
    periodos = [a * 100 + m for a in range(2019, 2025) for m in (3, 6, 9, 12)]

    linhas = []
    for i in range(n_instituicoes):
        cod = f"SINT{i:03d}"
        escala = 10 ** rng.uniform(8.5, 11.0)          # ativo entre ~3e8 e 1e11
        deriva = rng.normal(0.02, 0.01)
        desviante = i < max(2, n_instituicoes // 12)   # exercita o caminho de alerta

        ativo = escala
        carteira = ativo * rng.uniform(0.35, 0.65)
        pl = ativo * rng.uniform(0.08, 0.18)
        capital = pl * rng.uniform(0.6, 0.95)

        for t, p in enumerate(periodos):
            ativo *= 1 + deriva + rng.normal(0, 0.03)
            carteira *= 1 + deriva + rng.normal(0, 0.05) + (0.06 if desviante and t > 8 else 0)
            pl *= 1 + deriva * 0.5 + rng.normal(0, 0.02)

            inad = np.clip(rng.normal(0.045, 0.015) + (0.02 if desviante and t > 12 else 0), 0.005, 0.30)
            cobertura = rng.uniform(0.9, 1.4) * (0.55 if desviante and t > 12 else 1.0)
            carteira_eh = carteira * inad * rng.uniform(0.8, 1.4)
            provisao = carteira_eh * cobertura

            resultado_interm = carteira * rng.uniform(0.02, 0.05)
            despesa_prov = provisao * rng.uniform(0.15, 0.35)
            lucro = resultado_interm * rng.uniform(0.10, 0.35) - despesa_prov * 0.3

            linhas.append(
                {
                    "cod_inst": cod,
                    "anomes": p,
                    "ativo_total": ativo,
                    "disponibilidades": ativo * rng.uniform(0.03, 0.10),
                    "tvm": ativo * rng.uniform(0.10, 0.30),
                    "carteira_credito": carteira,
                    "provisao_pcld": provisao,
                    "carteira_eh": carteira_eh,
                    "outros_creditos": ativo * rng.uniform(0.02, 0.09),
                    "creditos_tributarios": pl * rng.uniform(0.05, 0.30) * (2.0 if desviante else 1.0),
                    "imobilizado": ativo * rng.uniform(0.005, 0.03),
                    "intangivel": ativo * rng.uniform(0.001, 0.02),
                    "captacoes": ativo * rng.uniform(0.55, 0.80),
                    "passivo_total": ativo - pl,
                    "patrimonio_liquido": pl,
                    "capital_social": capital * (1.15 if (desviante and t == 14) else 1.0),
                    "lucro_liquido": lucro,
                    "receita_intermediacao": resultado_interm * rng.uniform(1.5, 2.5),
                    "despesa_intermediacao": resultado_interm * rng.uniform(0.5, 1.5),
                    "resultado_intermediacao": resultado_interm,
                    "despesa_provisao": despesa_prov,
                    "receita_servicos": resultado_interm * rng.uniform(0.1, 0.4),
                    "despesa_administrativa": resultado_interm * rng.uniform(0.4, 0.8),
                    "outras_receitas_op": resultado_interm * rng.uniform(0.02, 0.15) * (3.0 if desviante else 1.0),
                    "indice_basileia": np.clip(rng.normal(15, 3) - (3.5 if desviante and t > 12 else 0), 8, 40),
                    "inadimplencia": inad,
                    "segmento": "S2" if i < n_instituicoes // 4 else "S3",
                }
            )
    df = pd.DataFrame(linhas)
    df.attrs["AVISO"] = AVISO
    return df


def eventos_artificiais(painel: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Eventos fictícios para exercitar o caminho de validação externa."""
    codigos = sorted(painel["cod_inst"].unique())[:n]
    return pd.DataFrame(
        {
            "cod_inst": codigos,
            "anomes_evento": [202312, 202406, 202409][:n],
            "tipo_evento": ["FICTICIO"] * len(codigos),
            "fonte": ["fixture_fumaca.py — NAO E FONTE REAL"] * len(codigos),
        }
    )
