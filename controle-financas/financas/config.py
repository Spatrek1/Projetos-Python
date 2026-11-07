"""Leitura de configuração a partir de variáveis de ambiente / arquivo .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv é opcional
    def load_dotenv(*_args, **_kwargs):
        return False


@dataclass(frozen=True)
class Config:
    provedor: str = "fake"
    pluggy_client_id: str = ""
    pluggy_client_secret: str = ""
    pluggy_item_ids: list[str] = field(default_factory=list)
    db_path: str = "financas.db"
    dias_iniciais: int = 365


def carregar_config() -> Config:
    load_dotenv()
    itens = [i.strip() for i in os.getenv("PLUGGY_ITEM_IDS", "").split(",") if i.strip()]
    return Config(
        provedor=os.getenv("FINANCAS_PROVEDOR", "fake").strip().lower(),
        pluggy_client_id=os.getenv("PLUGGY_CLIENT_ID", "").strip(),
        pluggy_client_secret=os.getenv("PLUGGY_CLIENT_SECRET", "").strip(),
        pluggy_item_ids=itens,
        db_path=os.getenv("FINANCAS_DB", "financas.db"),
        dias_iniciais=int(os.getenv("FINANCAS_DIAS_INICIAIS", "365")),
    )
