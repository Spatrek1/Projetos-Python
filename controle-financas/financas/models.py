"""Modelos de domínio. Valores monetários sempre em centavos (int)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

DEBITO = "DEBITO"   # saída de dinheiro (gasto)
CREDITO = "CREDITO"  # entrada de dinheiro (receita)


@dataclass
class Conta:
    id: str
    item_id: str
    nome: str
    tipo: str  # BANK / CREDIT
    subtipo: str = ""
    numero: str = ""
    saldo_centavos: int = 0
    moeda: str = "BRL"


@dataclass
class Transacao:
    id: str
    conta_id: str
    data: date
    descricao: str
    valor_centavos: int  # sempre positivo; a direção vem de `tipo`
    tipo: str            # DEBITO ou CREDITO
    categoria_banco: str = ""
    status: str = "POSTED"
    moeda: str = "BRL"

    @property
    def eh_gasto(self) -> bool:
        return self.tipo == DEBITO


def para_centavos(valor) -> int:
    """Converte float/str/Decimal em centavos inteiros (positivo)."""
    d = Decimal(str(valor)).copy_abs() * 100
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def formatar_brl(centavos: int) -> str:
    """1234567 -> 'R$ 12.345,67'"""
    sinal = "-" if centavos < 0 else ""
    reais, cents = divmod(abs(centavos), 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{cents:02d}"


@dataclass
class Investimento:
    id: str
    item_id: str              # "manual" para investimentos cadastrados à mão
    nome: str
    tipo: str                 # FIXED_INCOME, MUTUAL_FUND, EQUITY, ETF, SECURITY, COE, OTHER
    subtipo: str = ""         # CDB, LCI, TREASURY, STOCK, ...
    codigo: str = ""          # ticker / código do ativo
    saldo_centavos: int = 0   # valor líquido atual
    valor_bruto_centavos: int | None = None
    valor_aplicado_centavos: int | None = None
    quantidade: float | None = None
    vencimento: date | None = None
    taxa: str = ""            # ex.: "110% CDI", "IPCA + 6%"
    instituicao: str = ""
    moeda: str = "BRL"

    @property
    def rendimento_centavos(self) -> int | None:
        if self.valor_aplicado_centavos is None:
            return None
        return self.saldo_centavos - self.valor_aplicado_centavos


TIPOS_INVESTIMENTO = {
    "FIXED_INCOME": "Renda fixa",
    "MUTUAL_FUND": "Fundos",
    "EQUITY": "Ações",
    "ETF": "ETFs",
    "SECURITY": "Previdência",
    "COE": "COE",
    "CRYPTO": "Criptomoedas",  # só para cadastro manual
    "OTHER": "Outros",
}


def nome_tipo_investimento(tipo: str) -> str:
    return TIPOS_INVESTIMENTO.get((tipo or "").upper(), tipo or "Outros")
