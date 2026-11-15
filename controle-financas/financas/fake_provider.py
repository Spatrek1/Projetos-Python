"""Provedor com dados fictícios, para testar sem credenciais do Open Finance."""

from __future__ import annotations

import random
from datetime import date, timedelta

from financas.models import CREDITO, DEBITO, Conta, Investimento, Transacao

_GASTOS = [
    ("IFOOD *RESTAURANTE", "Food delivery", 25, 90),
    ("UBER *TRIP", "Taxi and ride-hailing", 12, 45),
    ("SUPERMERCADO PAO DE ACUCAR", "Groceries", 80, 450),
    ("POSTO SHELL", "Gas stations", 100, 250),
    ("NETFLIX.COM", "Video streaming", 39.9, 39.9),
    ("SPOTIFY", "Music streaming", 21.9, 21.9),
    ("DROGASIL", "Pharmacy", 20, 150),
    ("CONTA DE LUZ ENEL", "Electricity", 120, 260),
    ("AMAZON MARKETPLACE", "Online shopping", 30, 300),
    ("PIX ENVIADO JOAO", "Transfer - PIX", 50, 200),
]


class FakeProvider:
    def __init__(self, semente: int = 42):
        self.semente = semente

    def listar_contas(self) -> list[Conta]:
        return [
            Conta(id="fake-cc", item_id="fake", nome="Conta Corrente Fake", tipo="BANK",
                  subtipo="CHECKING_ACCOUNT", numero="0001-1", saldo_centavos=523_410),
            Conta(id="fake-cartao", item_id="fake", nome="Cartão Fake", tipo="CREDIT",
                  subtipo="CREDIT_CARD", numero="**** 1234", saldo_centavos=-182_000),
        ]

    def listar_transacoes(self, conta_id: str, desde: date, ate: date) -> list[Transacao]:
        resultado: list[Transacao] = []
        dia = desde
        while dia <= ate:
            # semente por (conta, dia) => dados estáveis entre sincronizações
            rng = random.Random(f"{self.semente}-{conta_id}-{dia.isoformat()}")
            if conta_id == "fake-cc" and dia.day == 5:
                resultado.append(Transacao(
                    id=f"{conta_id}-{dia}-salario", conta_id=conta_id, data=dia,
                    descricao="SALARIO EMPRESA XYZ", valor_centavos=750_000,
                    tipo=CREDITO, categoria_banco="Salary"))
            for n in range(rng.choices([0, 1, 2], weights=[5, 3, 1])[0]):
                desc, cat, vmin, vmax = rng.choice(_GASTOS)
                valor = round(rng.uniform(vmin, vmax), 2)
                resultado.append(Transacao(
                    id=f"{conta_id}-{dia}-{n}", conta_id=conta_id, data=dia,
                    descricao=desc, valor_centavos=round(valor * 100),
                    tipo=DEBITO, categoria_banco=cat))
            dia += timedelta(days=1)
        return resultado

    def listar_investimentos(self) -> list[Investimento]:
        return [
            Investimento(id="fake-cdb", item_id="fake", nome="CDB Banco Fake 2028",
                         tipo="FIXED_INCOME", subtipo="CDB", saldo_centavos=1_087_350,
                         valor_bruto_centavos=1_103_200, valor_aplicado_centavos=1_000_000,
                         vencimento=date(2028, 6, 15), taxa="110% CDI",
                         instituicao="Banco Fake"),
            Investimento(id="fake-tesouro", item_id="fake", nome="Tesouro IPCA+ 2035",
                         tipo="FIXED_INCOME", subtipo="TREASURY", saldo_centavos=532_180,
                         valor_aplicado_centavos=500_000, quantidade=1.8,
                         vencimento=date(2035, 5, 15), taxa="IPCA + 6.1% a.a.",
                         instituicao="Tesouro Nacional"),
            Investimento(id="fake-fundo", item_id="fake", nome="Fundo Multimercado Fake",
                         tipo="MUTUAL_FUND", subtipo="MULTIMARKET_FUND",
                         saldo_centavos=254_900, valor_aplicado_centavos=260_000,
                         quantidade=1520.4, instituicao="Gestora Fake"),
            Investimento(id="fake-acao", item_id="fake", nome="Ação Fake ON", codigo="FAKE3",
                         tipo="EQUITY", subtipo="STOCK", saldo_centavos=318_000,
                         valor_aplicado_centavos=290_000, quantidade=100,
                         instituicao="Corretora Fake"),
        ]
