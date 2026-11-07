"""Categorização de transações.

Ordem de prioridade:
  1. Categoria definida manualmente pelo usuário (nunca é sobrescrita)
  2. Regras do usuário (texto contido na descrição -> categoria)
  3. Mapeamento da categoria que o banco/Pluggy enviou
  4. "Outros"
"""

from __future__ import annotations

import unicodedata

OUTROS = "Outros"

# Trechos (minúsculos, sem acento) da categoria do banco -> categoria em PT
MAPA_CATEGORIA_BANCO: list[tuple[str, str]] = [
    ("salary", "Salário"),
    ("income", "Receitas"),
    ("food delivery", "Alimentação"),
    ("restaurant", "Alimentação"),
    ("eating out", "Alimentação"),
    ("groceries", "Mercado"),
    ("supermarket", "Mercado"),
    ("gas station", "Transporte"),
    ("taxi", "Transporte"),
    ("ride", "Transporte"),
    ("transport", "Transporte"),
    ("parking", "Transporte"),
    ("pharmacy", "Saúde"),
    ("health", "Saúde"),
    ("electricity", "Moradia"),
    ("water", "Moradia"),
    ("rent", "Moradia"),
    ("housing", "Moradia"),
    ("telecom", "Moradia"),
    ("internet", "Moradia"),
    ("streaming", "Assinaturas"),
    ("subscription", "Assinaturas"),
    ("education", "Educação"),
    ("shopping", "Compras"),
    ("clothing", "Compras"),
    ("electronics", "Compras"),
    ("travel", "Viagem"),
    ("airline", "Viagem"),
    ("tax", "Impostos e Taxas"),
    ("bank fees", "Impostos e Taxas"),
    ("interest", "Impostos e Taxas"),
    ("investment", "Investimentos"),
    ("transfer", "Transferências"),
    ("leisure", "Lazer"),
    ("entertainment", "Lazer"),
]


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower().strip()


def categoria_por_banco(categoria_banco: str) -> str | None:
    alvo = normalizar(categoria_banco)
    if not alvo:
        return None
    for trecho, categoria in MAPA_CATEGORIA_BANCO:
        if trecho in alvo:
            return categoria
    return None


def categorizar(descricao: str, categoria_banco: str,
                regras: list[tuple[str, str]]) -> str:
    """`regras` é uma lista de (padrao, categoria), na ordem de prioridade."""
    desc = normalizar(descricao)
    for padrao, categoria in regras:
        if normalizar(padrao) in desc:
            return categoria
    return categoria_por_banco(categoria_banco) or OUTROS
