from datetime import date

from financas.fake_provider import FakeProvider
from financas.models import Investimento
from financas.pluggy_client import converter_investimento
from financas.relatorios import carteira, patrimonio
from financas.sync import sincronizar


def test_converter_investimento_pluggy():
    inv = converter_investimento({
        "id": "i1", "name": "CDB X", "type": "FIXED_INCOME", "subtype": "CDB",
        "balance": 2000, "amount": 2500, "amountOriginal": 1800, "rate": 110,
        "rateType": "CDI", "dueDate": "2028-01-10T00:00:00.000Z", "issuer": "Banco X",
        "taxes": None,
    }, "item1")
    assert inv.saldo_centavos == 200_000
    assert inv.valor_bruto_centavos == 250_000
    assert inv.rendimento_centavos == 20_000
    assert inv.vencimento == date(2028, 1, 10)
    assert inv.taxa == "110% CDI"


def test_converter_investimento_campos_ausentes():
    inv = converter_investimento({"id": "i2", "amount": 10.5}, "item1")
    assert inv.saldo_centavos == 1050 and inv.tipo == "OTHER"
    assert inv.valor_aplicado_centavos is None and inv.rendimento_centavos is None


def test_sync_traz_investimentos_e_patrimonio(banco):
    r = sincronizar(banco, FakeProvider(), desde=date(2026, 11, 1), ate=date(2026, 11, 7))
    assert r.investimentos == 4
    c = carteira(banco)
    assert c.total == 1_087_350 + 532_180 + 254_900 + 318_000
    assert set(c.grupos) == {"Renda fixa", "Fundos", "Ações"}
    p = patrimonio(banco)
    assert p.liquido == p.contas + p.investimentos - p.cartoes


class ProvedorQueResgata(FakeProvider):
    def __init__(self):
        super().__init__()
        self.item_ids = ["fake"]
        self.chamadas = 0

    def listar_investimentos(self):
        self.chamadas += 1
        todos = super().listar_investimentos()
        return todos if self.chamadas == 1 else todos[1:]


def test_investimento_resgatado_fica_inativo(banco):
    p = ProvedorQueResgata()
    sincronizar(banco, p, desde=date(2026, 11, 1), ate=date(2026, 11, 7))
    r = sincronizar(banco, p, desde=date(2026, 11, 1), ate=date(2026, 11, 8))
    assert r.investimentos_resgatados == 1
    assert len(banco.listar_investimentos()) == 3


def test_manual_nao_e_desativado_pela_sync(banco):
    banco.salvar_investimento(Investimento(id="manual-1", item_id="manual", nome="Bitcoin",
                                           tipo="OTHER", saldo_centavos=50_000))
    sincronizar(banco, FakeProvider(), desde=date(2026, 11, 1), ate=date(2026, 11, 7))
    assert banco.buscar_investimento("manual-1")["ativo"] == 1


def test_evolucao_mensal(banco):
    inv = Investimento(id="x", item_id="manual", nome="X", tipo="ETF", saldo_centavos=100)
    banco.salvar_investimento(inv, data_foto=date(2026, 9, 30))
    inv.saldo_centavos = 150
    banco.salvar_investimento(inv, data_foto=date(2026, 10, 15))
    inv.saldo_centavos = 170
    banco.salvar_investimento(inv, data_foto=date(2026, 10, 31))
    ev = [(e["mes"], e["total_centavos"]) for e in banco.evolucao_investimentos()]
    assert ev == [("2026-09", 100), ("2026-10", 170)]


def test_fiis_tem_grupo_proprio(banco):
    for i, (sub, nome) in enumerate([("STOCK", "PETR4"), ("REAL_ESTATE_FUND", "HGLG11"),
                                     ("ETF", "BOVA11")]):
        banco.salvar_investimento(Investimento(id=f"e{i}", item_id="manual", nome=nome,
                                               tipo="EQUITY", subtipo=sub, saldo_centavos=100))
    assert set(carteira(banco).grupos) == {"Ações", "FIIs", "ETFs"}
