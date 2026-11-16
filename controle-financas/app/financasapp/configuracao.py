"""Configuração do app no celular: chaves da Pluggy e IDs das conexões.

Fica num JSON dentro da área privada do app (outros apps não leem). Nunca vai
para o git: o arquivo só existe no aparelho.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ConfigApp:
    client_id: str = ""
    client_secret: str = ""
    item_ids: list[str] = field(default_factory=list)
    dias_iniciais: int = 365

    @property
    def completa(self) -> bool:
        return bool(self.client_id and self.client_secret and self.item_ids)


def separar_ids(texto: str) -> list[str]:
    """Aceita IDs separados por vírgula, espaço ou linha; ignora repetidos.

    Se colarem um link (ex.: .../connections/<id>), fica só o final.
    """
    ids: list[str] = []
    for parte in re.split(r"[\s,;]+", texto or ""):
        parte = parte.strip().rstrip("/")
        if not parte:
            continue
        parte = parte.rsplit("/", 1)[-1].split("?", 1)[0]
        if parte and parte not in ids:
            ids.append(parte)
    return ids


def carregar(caminho: Path | str) -> ConfigApp:
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ConfigApp()
    try:
        dias = int(dados.get("dias_iniciais") or 365)
    except (TypeError, ValueError):
        dias = 365
    return ConfigApp(
        client_id=str(dados.get("client_id") or "").strip(),
        client_secret=str(dados.get("client_secret") or "").strip(),
        item_ids=[str(i).strip() for i in dados.get("item_ids") or [] if str(i).strip()],
        dias_iniciais=dias,
    )


def salvar(caminho: Path | str, cfg: ConfigApp) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(asdict(cfg), ensure_ascii=False), encoding="utf-8")
    temporario.replace(caminho)  # grava inteiro ou nada
