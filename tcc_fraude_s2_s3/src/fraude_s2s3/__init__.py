"""Detecção de atipicidade contábil em instituições financeiras S2 e S3.

Pacote de apoio ao TCC "Auditorias em instituições financeiras dos segmentos
S2 e S3", com dados públicos do IF.data/COSIF (Banco Central do Brasil).

Aviso metodológico que atravessa todo o pacote
----------------------------------------------
Nenhuma função aqui detecta fraude. O que se mede é **atipicidade contábil**:
distância entre o comportamento observado de uma instituição e o padrão dos
seus pares e do seu próprio histórico. Fraude é qualificação jurídica; exige
prova, contraditório e decisão de autoridade competente. A confusão entre as
duas coisas é o erro mais grave que este tipo de trabalho pode cometer, e o
pacote foi escrito para tornar essa confusão difícil.
"""

from . import (avaliacao, baselines, benford, config, diagnostico,
               ifdata, indicadores, interpretacao, mapeamento, painel,
               redes, segmentacao, vazamento)

__all__ = [
    "avaliacao", "baselines", "benford", "config", "diagnostico", "ifdata",
    "indicadores", "interpretacao", "mapeamento", "painel", "redes",
    "segmentacao", "vazamento",
]

__version__ = "0.1.0"
