"""Coloca ``src/`` e ``testes/`` no caminho de importacao.

Permite rodar ``pytest`` de qualquer diretorio sem instalar o pacote e sem
depender do ``sys.path.insert`` de cada arquivo de teste.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
for sub in ("src", "testes"):
    caminho = str(RAIZ / sub)
    if caminho not in sys.path:
        sys.path.insert(0, caminho)
