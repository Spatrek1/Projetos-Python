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
PAGAMENTO_FATURA = "Pagamento de fatura"
ENTRE_CONTAS = "Entre contas próprias"
INVESTIMENTOS = "Investimentos"

# Movimentações que só mudam o dinheiro de lugar: não são gasto nem receita.
# Ex.: pagar a fatura (as compras já contam no cartão), PIX para outra conta sua,
# aplicar/resgatar investimentos. O resumo mostra essas à parte.
CATEGORIAS_FORA_DO_TOTAL = frozenset({PAGAMENTO_FATURA, ENTRE_CONTAS, INVESTIMENTOS})

# Trechos (minúsculos, sem acento) da categoria do banco -> categoria em PT.
# A ORDEM IMPORTA: vence o primeiro trecho contido. Os específicos vêm antes
# dos genéricos (ex.: "fixed income" antes de "income", "dividend" antes de
# "interest", "taxi" antes de "tax", "same person transfer" antes de "transfer").
MAPA_CATEGORIA_BANCO: list[tuple[str, str]] = [
    # --- movimentações fora do total
    ("credit card payment", PAGAMENTO_FATURA),
    ("same person transfer", ENTRE_CONTAS),
    ("transfer - internal", ENTRE_CONTAS),
    ("fixed income", INVESTIMENTOS),
    ("investment", INVESTIMENTOS),
    # --- receitas
    ("salary", "Salário"),
    ("dividend", "Rendimentos"),
    ("proceeds", "Rendimentos"),
    ("income tax", "Impostos e Taxas"),
    ("cashback", "Receitas"),
    ("income", "Receitas"),
    # --- gastos
    ("food delivery", "Alimentação"),
    ("restaurant", "Alimentação"),
    ("eating out", "Alimentação"),
    ("food and drinks", "Alimentação"),
    ("groceries", "Mercado"),
    ("supermarket", "Mercado"),
    ("gas station", "Transporte"),
    ("taxi", "Transporte"),
    ("ride", "Transporte"),
    ("transport", "Transporte"),
    ("parking", "Transporte"),
    ("pharmacy", "Saúde"),
    ("health", "Saúde"),
    ("wellness", "Saúde"),
    ("fitness", "Saúde"),
    ("gym", "Saúde"),
    ("insurance", "Seguros"),
    ("electricity", "Moradia"),
    ("water", "Moradia"),
    ("utilities", "Moradia"),
    ("rent", "Moradia"),
    ("housing", "Moradia"),
    ("houseware", "Moradia"),
    ("telecom", "Moradia"),
    ("internet", "Moradia"),
    ("streaming", "Assinaturas"),
    ("subscription", "Assinaturas"),
    ("digital services", "Assinaturas"),
    ("education", "Educação"),
    ("school", "Educação"),
    ("online course", "Educação"),
    ("bookstore", "Educação"),
    ("shopping", "Compras"),
    ("clothing", "Compras"),
    ("electronics", "Compras"),
    ("office supplies", "Compras"),
    ("pet supplies", "Pets"),
    ("travel", "Viagem"),
    ("airline", "Viagem"),
    ("late payment", "Impostos e Taxas"),
    ("overdraft", "Impostos e Taxas"),
    ("tax", "Impostos e Taxas"),
    ("bank fees", "Impostos e Taxas"),
    ("interest", "Impostos e Taxas"),   # juros cobrados ("Interests charged")
    ("donation", "Doações"),
    ("transfer", "Transferências"),
    ("leisure", "Lazer"),
    ("entertainment", "Lazer"),
    ("cinema", "Lazer"),
    ("ticket", "Lazer"),
    ("services", "Serviços"),
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
