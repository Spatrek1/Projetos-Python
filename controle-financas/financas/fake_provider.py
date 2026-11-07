"""Provedor com dados fictícios, para testar sem credenciais do Open Finance."""

from __future__ import annotations

import random
from datetime import date, timedelta

from financas.models import CREDITO, DEBITO, Conta, Transacao

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
