# CLAUDE.md — Controle de Finanças (Open Finance)

Contexto para o Claude Code (VS Code / CLI) trabalhar neste projeto.

## O que é
CLI em Python que conecta ao **Open Finance Brasil** através da **Pluggy**
(agregador certificado pelo Banco Central), baixa contas e transações e grava
tudo em um **SQLite local**, categorizando cada gasto automaticamente.

## Comandos
```bash
pip install -r requirements.txt
python -m pytest -q                       # testes (não usam rede)
python -m financas sincronizar --fake     # dados fictícios, sem credenciais
python -m financas sincronizar            # Open Finance real (precisa do .env)
python -m financas resumo --mes 2026-11
python -m financas gastos --mes 2026-11 --categoria Mercado
```

## Arquitetura (`financas/`)
- `config.py` — lê `.env` (`FINANCAS_PROVEDOR`, `PLUGGY_*`, `FINANCAS_DB`).
- `models.py` — `Conta`, `Transacao`, helpers `para_centavos` / `formatar_brl`.
- `provedores.py` — `Provedor` (Protocol) + `criar_provedor(config)`.
- `pluggy_client.py` — cliente HTTP da API Pluggy (`/auth`, `/accounts`, `/transactions`).
- `fake_provider.py` — dados determinísticos para dev/testes.
- `db.py` — classe `Banco`: schema SQLite e todas as queries.
- `categorias.py` — regra de categorização (manual > regra do usuário > categoria do banco > "Outros").
- `sync.py` — `sincronizar()` (incremental, upsert) e `recategorizar()`.
- `relatorios.py` — resumo mensal e exportação CSV.
- `cli.py` — argparse; cada subcomando é uma função `cmd_*`.

## Convenções (siga sempre)
- **Dinheiro é `int` em centavos**, sempre positivo; a direção vem de `tipo` (`DEBITO` = gasto, `CREDITO` = receita). Nunca use `float` para somar valores.
- Código, nomes e mensagens em **português**.
- Sincronização deve ser **idempotente**: rodar duas vezes não duplica nada (PK = id da transação na Pluggy).
- `categoria_manual = 1` nunca pode ser sobrescrita por sync ou regras.
- Novos provedores implementam `listar_contas()` e `listar_transacoes(conta_id, desde, ate)` e são registrados em `criar_provedor`.
- Testes nunca chamam a rede: use `FakeProvider` ou uma sessão HTTP falsa (veja `tests/test_pluggy_client.py`).
- Toda funcionalidade nova vem com teste em `tests/`.

## Segurança
- Nunca leia, imprima, logue ou faça commit de `.env`, `PLUGGY_CLIENT_SECRET` ou da `apiKey`.
- `*.db` e `*.csv` contêm dados financeiros reais — estão no `.gitignore`, não remova.
- Acesso é somente leitura: não implemente iniciação de pagamentos/PIX.

## Ideias de próximos passos
- Dashboard web (Streamlit/FastAPI) lendo o mesmo SQLite.
- Agendamento diário (`cron` / Agendador de Tarefas) de `python -m financas sincronizar`.
- Detecção de assinaturas recorrentes e alertas de orçamento por e-mail/Telegram.
- Webhooks da Pluggy (`item/updated`) para sincronizar em tempo real.
