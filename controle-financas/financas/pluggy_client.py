"""Cliente da API da Pluggy (agregador certificado do Open Finance Brasil).

Docs: https://docs.pluggy.ai
Fluxo:
  1. POST /auth com clientId/clientSecret -> apiKey (válida por ~2h)
  2. GET /accounts?itemId=...            -> contas de cada conexão (item)
  3. GET /transactions?accountId=...      -> transações paginadas
"""

from __future__ import annotations

import time
from datetime import date, datetime

import requests

from financas.models import CREDITO, DEBITO, Conta, Transacao, para_centavos

BASE_URL = "https://api.pluggy.ai"
TTL_API_KEY = 110 * 60  # renova um pouco antes das 2h


class PluggyError(RuntimeError):
    pass


class PluggyClient:
    def __init__(self, client_id: str, client_secret: str, item_ids: list[str],
                 session: requests.Session | None = None, base_url: str = BASE_URL,
                 timeout: float = 30.0):
        if not client_id or not client_secret:
            raise PluggyError("Defina PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET no .env")
        if not item_ids:
            raise PluggyError("Defina PLUGGY_ITEM_IDS no .env (IDs das conexões bancárias)")
        self.client_id = client_id
        self.client_secret = client_secret
        self.item_ids = item_ids
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._api_key: str | None = None
        self._api_key_em = 0.0

    # ------------------------------------------------------------------ HTTP
    def _autenticar(self) -> str:
        if self._api_key and time.monotonic() - self._api_key_em < TTL_API_KEY:
            return self._api_key
        resp = self.session.post(
            f"{self.base_url}/auth",
            json={"clientId": self.client_id, "clientSecret": self.client_secret},
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise PluggyError(f"Falha na autenticação Pluggy ({resp.status_code}): {resp.text}")
        self._api_key = resp.json()["apiKey"]
        self._api_key_em = time.monotonic()
        return self._api_key

    def _get(self, caminho: str, params: dict | None = None) -> dict:
        headers = {"X-API-KEY": self._autenticar()}
        resp = self.session.get(f"{self.base_url}{caminho}", params=params,
                                headers=headers, timeout=self.timeout)
        if resp.status_code == 401:  # chave expirou: renova e tenta de novo
            self._api_key = None
            headers = {"X-API-KEY": self._autenticar()}
            resp = self.session.get(f"{self.base_url}{caminho}", params=params,
                                    headers=headers, timeout=self.timeout)
        if resp.status_code >= 400:
            raise PluggyError(f"GET {caminho} falhou ({resp.status_code}): {resp.text}")
        return resp.json()

    # --------------------------------------------------------------- domínio
    def listar_contas(self) -> list[Conta]:
        contas: list[Conta] = []
        for item_id in self.item_ids:
            dados = self._get("/accounts", {"itemId": item_id})
            for c in dados.get("results", []):
                contas.append(Conta(
                    id=c["id"],
                    item_id=item_id,
                    nome=c.get("marketingName") or c.get("name") or "Conta",
                    tipo=c.get("type", ""),
                    subtipo=c.get("subtype") or "",
                    numero=c.get("number") or "",
                    saldo_centavos=round((c.get("balance") or 0) * 100),
                    moeda=c.get("currencyCode") or "BRL",
                ))
        return contas

    def listar_transacoes(self, conta_id: str, desde: date, ate: date) -> list[Transacao]:
        transacoes: list[Transacao] = []
        pagina = 1
        while True:
            dados = self._get("/transactions", {
                "accountId": conta_id,
                "from": desde.isoformat(),
                "to": ate.isoformat(),
                "pageSize": 500,
                "page": pagina,
            })
            transacoes.extend(converter_transacao(t, conta_id) for t in dados.get("results", []))
            if pagina >= int(dados.get("totalPages") or 1):
                break
            pagina += 1
        return transacoes


def converter_transacao(t: dict, conta_id: str) -> Transacao:
    """Converte o JSON da Pluggy no nosso modelo.

    A direção é dada pelo campo `type` (DEBIT/CREDIT); o sinal de `amount`
    varia entre conta corrente e cartão, por isso usamos o valor absoluto.
    """
    tipo_api = (t.get("type") or "").upper()
    if tipo_api in ("DEBIT", "CREDIT"):
        tipo = DEBITO if tipo_api == "DEBIT" else CREDITO
    else:
        tipo = DEBITO if float(t.get("amount") or 0) < 0 else CREDITO
    data_txt = t["date"]
    data = datetime.fromisoformat(data_txt.replace("Z", "+00:00")).date()
    return Transacao(
        id=t["id"],
        conta_id=t.get("accountId") or conta_id,
        data=data,
        descricao=(t.get("description") or t.get("descriptionRaw") or "").strip(),
        valor_centavos=para_centavos(t.get("amount") or 0),
        tipo=tipo,
        categoria_banco=t.get("category") or "",
        status=t.get("status") or "POSTED",
        moeda=t.get("currencyCode") or "BRL",
    )
