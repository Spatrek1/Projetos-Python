"""Parâmetros centrais do estudo.

Todo valor que representa uma *decisão metodológica* está aqui, isolado do
código, para que a banca possa auditar as escolhas sem ler implementação.

Referências normativas dos limiares de segmentação:
    Resolução CMN nº 4.553/2017 (segmentação S1–S5 por Exposição/PIB).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_BRUTOS = RAIZ / "dados" / "ifdata_bruto"
DIR_PROCESSADOS = RAIZ / "dados" / "tratados"
DIR_EXTERNOS = RAIZ / "dados" / "externos"
DIR_RESULTADOS = RAIZ / "resultados"


# ---------------------------------------------------------------------------
# 1. Recorte amostral
# ---------------------------------------------------------------------------

#: Trimestres COSIF publicados no IF.data (formato AAAAMM).
#: O IF.data publica dados em base trimestral: 03, 06, 09 e 12.
ANOS = tuple(range(2019, 2025))          # 2019..2024 -> 24 trimestres
MESES_TRIMESTRAIS = (3, 6, 9, 12)

#: Segmentos analisados. Restrição imposta pelo escopo da pesquisa.
SEGMENTOS_ALVO = ("S2", "S3")

#: Limiares de Exposição/PIB da Resolução CMN 4.553/2017 usados quando a
#: classificação oficial não estiver disponível (ver `segmentacao.py`).
#: São faixas [inferior, superior) sobre a razão Exposição/PIB.
FAIXAS_SEGMENTO = {
    "S1": (0.10, float("inf")),   # >= 10% do PIB (ou atuação internacional relevante)
    "S2": (0.01, 0.10),           # >= 1% e < 10%
    "S3": (0.001, 0.01),          # >= 0,1% e < 1%
    "S4": (0.0, 0.001),           # < 0,1%
}


#: Piso de capital regulatório de referência, em pontos percentuais do RWA.
#:
#: Instituições sujeitas ao regime pleno de Basileia têm requerimento mínimo
#: acrescido dos adicionais de capital principal. Cooperativas de crédito
#: enquadradas em regime prudencial simplificado observam requerimento próprio,
#: situado em uma faixa e não em valor único.
#:
#: Como a posição exata de cada cooperativa dentro da faixa depende do seu
#: enquadramento — informação que o IF.data não publica nos relatórios do
#: recorte —, o pipeline calcula a folga contra os DOIS extremos e sinaliza as
#: observações em que a conclusão depende dessa escolha. Ver PONTO DE CORREÇÃO
#: registrado por `indicadores.construir()`.
PISO_BASILEIA_GERAL = 10.5
PISO_BASILEIA_COOPERATIVA = (13.0, 18.0)

#: Códigos de "Tipo de Consolidado Bancário" (TCB) que identificam cooperativas
#: de crédito, conforme a legenda publicada pelo próprio IF.data:
#:   b3S — Cooperativa de Crédito Singulares
#:   b3C — Central e Confederação de Cooperativas de Crédito
TCB_COOPERATIVAS = ("b3S", "b3C")


# ---------------------------------------------------------------------------
# 2. Coleta
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfigColeta:
    """Configuração da extração no IF.data.

    ``base_url`` e ``recursos_candidatos`` são deliberadamente *candidatos*:
    o módulo :mod:`fraude_s2s3.ifdata` valida cada um contra o documento
    ``$metadata`` do serviço antes de usar. Nada aqui é tratado como verdade
    sem confirmação em tempo de execução (ver PONTO DE CORREÇÃO 1).
    """

    base_url: str = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"
    timeout_s: int = 120
    tentativas: int = 4
    espera_inicial_s: float = 2.0
    formato: str = "json"
    usar_cache: bool = True

    #: Nomes de recurso (EntitySet/FunctionImport) que já foram observados em
    #: documentação pública do serviço. A ordem é de preferência.
    recursos_candidatos: tuple[str, ...] = (
        "IfDataValores",
        "IfDataCadastro",
        "IfDataMesesDisponiveis",
        "ListaDeRelatorios",
    )

    #: "Tipo de instituição" no IF.data separa conglomerados prudenciais de
    #: instituições independentes. Os códigos exatos são descobertos em
    #: execução; estes são apenas os valores a testar.
    tipos_instituicao_candidatos: tuple[int, ...] = (1, 2, 3, 4)


# ---------------------------------------------------------------------------
# 3. Painel e tratamento
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfigPainel:
    #: Winsorização simétrica dos indicadores contínuos, por trimestre.
    #: Contas COSIF produzem caudas extremas (o próprio artigo de referência
    #: reporta curtose > 29.000 no DF-Score); winsorizar é pré-requisito para
    #: qualquer modelo baseado em distância ou gradiente.
    winsor_inferior: float = 0.01
    winsor_superior: float = 0.99

    #: Fração máxima de ausências tolerada por indicador; acima disso o
    #: indicador é descartado e reportado como ponto de correção.
    max_ausentes_indicador: float = 0.40

    #: Número mínimo de trimestres observados para a instituição entrar no painel.
    min_trimestres_instituicao: int = 8

    #: Normalização: "rank_gauss" (robusta a outliers) ou "zscore".
    normalizacao: str = "rank_gauss"

    #: Z-score adicional calculado *dentro* de (segmento, trimestre), tornando
    #: a atipicidade relativa aos pares e não ao histórico global.
    z_score_por_pares: bool = True

    #: Janela para modelos sequenciais (nº de trimestres de contexto).
    janela_temporal: int = 4


# ---------------------------------------------------------------------------
# 4. Modelos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfigRede:
    """Hiperparâmetros da rede neural.

    A capacidade é deliberadamente pequena. O painel S2+S3 tem ordem de
    10^2 instituições x 24 trimestres; redes largas memorizam o painel e o
    erro de reconstrução deixa de discriminar (ver HISTORICO.md, seção 4).
    """

    dims_encoder: tuple[int, ...] = (64, 32)
    dim_latente: int = 8
    dropout: float = 0.2
    ruido_denoising: float = 0.10      # desvio do ruído gaussiano na entrada
    taxa_aprendizado: float = 1e-3
    weight_decay: float = 1e-4
    epocas: int = 400
    paciencia: int = 40                # early stopping
    lote: int = 64
    sementes: tuple[int, ...] = (0, 1, 2, 3, 4)   # ensemble p/ medir estabilidade

    # Modelo sequencial (GRU)
    dim_oculta_gru: int = 32
    camadas_gru: int = 1


@dataclass(frozen=True)
class ConfigAvaliacao:
    #: Percentil a partir do qual a instituição-trimestre é sinalizada.
    percentil_alerta: float = 0.95

    #: k usados em Precision@k / Recall@k na validação por eventos públicos.
    ks: tuple[int, ...] = (10, 25, 50, 100)

    #: Janela (em trimestres) anterior ao evento público em que um alerta é
    #: considerado "acerto antecipado". 4 trimestres = 1 ano de antecedência.
    janela_antecedencia: int = 4

    #: Corte temporal do treino. Nada posterior a esta data entra no ajuste.
    #: Painel é dado longitudinal: divisão aleatória vaza informação do futuro.
    corte_treino: int = 202212
    corte_validacao: int = 202312       # teste = 2024


@dataclass(frozen=True)
class Config:
    coleta: ConfigColeta = field(default_factory=ConfigColeta)
    painel: ConfigPainel = field(default_factory=ConfigPainel)
    rede: ConfigRede = field(default_factory=ConfigRede)
    avaliacao: ConfigAvaliacao = field(default_factory=ConfigAvaliacao)

    #: Se True, usa instituições fora de S2/S3 apenas para *pré-treino* do
    #: autoencoder (aprendizado da variedade de normalidade), pontuando
    #: exclusivamente S2/S3. Mantido DESLIGADO por padrão: o escopo declarado
    #: da pesquisa é S2/S3 exclusivamente. Ver HISTORICO.md, seção 4.3.
    pretreino_fora_do_escopo: bool = False


CONFIG = Config()


def periodos(anos=ANOS, meses=MESES_TRIMESTRAIS) -> list[int]:
    """Lista de períodos AAAAMM do recorte, em ordem cronológica."""
    return [ano * 100 + mes for ano in anos for mes in meses]
