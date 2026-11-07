"""Interface comum para fontes de dados bancários."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from financas.models import Conta, Transacao


class Provedor(Protocol):
    def listar_contas(self) -> list[Conta]: ...

    def listar_transacoes(self, conta_id: str, desde: date, ate: date) -> list[Transacao]: ...


def criar_provedor(config) -> Provedor:
    if config.provedor == "pluggy":
        from financas.pluggy_client import PluggyClient

        return PluggyClient(
            client_id=config.pluggy_client_id,
            client_secret=config.pluggy_client_secret,
            item_ids=config.pluggy_item_ids,
        )
    if config.provedor == "fake":
        from financas.fake_provider import FakeProvider

        return FakeProvider()
    raise ValueError(f"Provedor desconhecido: {config.provedor!r} (use 'pluggy' ou 'fake')")
