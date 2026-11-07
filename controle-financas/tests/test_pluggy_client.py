from datetime import date

import pytest

from financas.models import CREDITO, DEBITO
from financas.pluggy_client import PluggyClient, PluggyError, converter_transacao


class Resp:
    def __init__(self, status, dados):
        self.status_code = status
        self._dados = dados
        self.text = str(dados)

    def json(self):
        return self._dados


class SessaoFalsa:
    def __init__(self, paginas):
        self.paginas = paginas
        self.auth_calls = 0
        self.gets = []

    def post(self, url, json, timeout):
        self.auth_calls += 1
        assert url.endswith("/auth")
        return Resp(200, {"apiKey": "chave"})

    def get(self, url, params, headers, timeout):
        assert headers["X-API-KEY"] == "chave"
        self.gets.append((url, params))
        if url.endswith("/accounts"):
            return Resp(200, {"results": [{"id": "acc1", "name": "CC", "type": "BANK",
                                           "balance": 100.5}]})
        return Resp(200, self.paginas[params["page"] - 1])


def _tx(i, amount, tipo):
    return {"id": f"t{i}", "description": f"Compra {i}", "amount": amount, "type": tipo,
            "date": "2026-11-03T12:00:00.000Z", "category": "Groceries", "accountId": "acc1"}


def test_converter_transacao():
    t = converter_transacao(_tx(1, -45.9, "DEBIT"), "acc1")
    assert t.tipo == DEBITO and t.valor_centavos == 4590 and t.data == date(2026, 11, 3)
    t = converter_transacao(_tx(2, 1000, "CREDIT"), "acc1")
    assert t.tipo == CREDITO


def test_paginacao_e_cache_de_api_key():
    sessao = SessaoFalsa([
        {"totalPages": 2, "results": [_tx(1, -10, "DEBIT")]},
        {"totalPages": 2, "results": [_tx(2, -20, "DEBIT")]},
    ])
    cli = PluggyClient("id", "segredo", ["item1"], session=sessao)
    contas = cli.listar_contas()
    assert contas[0].saldo_centavos == 10050
    txs = cli.listar_transacoes("acc1", date(2026, 11, 1), date(2026, 11, 30))
    assert [t.id for t in txs] == ["t1", "t2"]
    assert sessao.auth_calls == 1


def test_exige_credenciais():
    with pytest.raises(PluggyError):
        PluggyClient("", "", ["x"])
