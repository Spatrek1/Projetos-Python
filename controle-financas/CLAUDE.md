# CLAUDE.md — Controle de Finanças (Open Finance)

Contexto para o Claude Code (VS Code / CLI) trabalhar neste projeto.

## O que é
CLI em Python que conecta ao **Open Finance Brasil** através da **Pluggy**
(agregador certificado pelo Banco Central), baixa contas, transações e **investimentos** e grava
tudo em um **SQLite local**, categorizando cada gasto automaticamente.

## Comandos
```bash
pip install -r requirements.txt
python -m pytest -q                       # testes (não usam rede)
python -m financas sincronizar --fake     # dados fictícios, sem credenciais
python -m financas sincronizar            # Open Finance real (precisa do .env)
python -m financas resumo --mes 2026-11
python -m financas gastos --mes 2026-11 --categoria Mercado
python -m financas investimentos          # carteira por tipo
python -m financas patrimonio             # contas + investimentos - cartões
python -m financas diagnostico            # testa .env e conexão Pluggy
```
Guia completo para o usuário: `GUIA.md`.

## Arquitetura (`financas/`)
- `config.py` — lê `.env` (`FINANCAS_PROVEDOR`, `PLUGGY_*`, `FINANCAS_DB`).
- `models.py` — `Conta`, `Transacao`, `Investimento`, helpers `para_centavos` / `formatar_brl`.
- `provedores.py` — `Provedor` (Protocol) + `criar_provedor(config)`.
- `pluggy_client.py` — cliente HTTP da API Pluggy (`/auth`, `/accounts`, `/v2/transactions`, `/investments`, `/items/{id}`).
  Campos da Pluggy podem vir `null`: sempre use `.get()`. O `/transactions` antigo responde 410:
  use `/v2/transactions` (`dateFrom`/`dateTo`, paginação por cursor `after` extraído de `next`).
  Dados reais vêm pelo conector **MeuPluggy** (gratuito, atualiza 1x/dia); IDs copiados do
  meu.pluggy.ai dão 404 — só valem os Item IDs da aplicação no dashboard.
- `fake_provider.py` — dados determinísticos para dev/testes.
- `db.py` — classe `Banco`: schema SQLite e todas as queries.
- `categorias.py` — regra de categorização (manual > regra do usuário > categoria do banco > "Outros").
  Em `MAPA_CATEGORIA_BANCO` **a ordem importa** (vence o primeiro trecho contido): específicos antes
  dos genéricos. `CATEGORIAS_FORA_DO_TOTAL` (fatura, entre contas próprias, investimentos) não conta
  como gasto/receita no resumo — evita contar o mesmo dinheiro duas vezes.
- `sync.py` — `sincronizar()` (incremental, upsert, inclui investimentos) e `recategorizar()`.
- `relatorios.py` — resumo mensal, `carteira()`, `patrimonio()` e exportação CSV.
- `cli.py` — argparse; cada subcomando é uma função `cmd_*`.

## Convenções (siga sempre)
- **Dinheiro é `int` em centavos**, sempre positivo; a direção vem de `tipo` (`DEBITO` = gasto, `CREDITO` = receita). Nunca use `float` para somar valores.
- Código, nomes e mensagens em **português**.
- Sincronização deve ser **idempotente**: rodar duas vezes não duplica nada (PK = id da transação na Pluggy).
- `categoria_manual = 1` nunca pode ser sobrescrita por sync ou regras.
- Novos provedores implementam `listar_contas()`, `listar_transacoes(conta_id, desde, ate)` e `listar_investimentos()` e são registrados em `criar_provedor`.
- Investimentos: `saldo_centavos` = valor líquido atual; `valor_aplicado_centavos` pode ser `None` (instituição não informou) — nunca trate como zero no rendimento.
- Investimentos com `item_id = 'manual'` são do usuário: a sync nunca os altera nem desativa. Os do Open Finance que somem viram `ativo = 0` (não apague — o histórico importa).
- `investimentos_historico` guarda uma foto por investimento por dia; é a base da evolução do patrimônio.
- A carteira agrupa por `nome_grupo_investimento(tipo, subtipo)`: FIIs/ETFs/BDRs vêm como `EQUITY` e se separam pelo subtipo.
- Testes nunca chamam a rede: use `FakeProvider` ou uma sessão HTTP falsa (veja `tests/test_pluggy_client.py`).
- Toda funcionalidade nova vem com teste em `tests/`.

## Segurança
- Nunca leia, imprima, logue ou faça commit de `.env`, `PLUGGY_CLIENT_SECRET` ou da `apiKey`.
- `*.db`, `*.csv` e `*.log` contêm dados financeiros reais — estão no `.gitignore`, não remova.
- Acesso é somente leitura: não implemente iniciação de pagamentos/PIX.

## Ideias de próximos passos
- Dashboard web (Streamlit/FastAPI) lendo o mesmo SQLite.
- Comparar rentabilidade da carteira com CDI/IPCA (API do Banco Central — SGS).
- Importar transações de investimento (`/investments/{id}/transactions`) para calcular aportes mensais.
- Detecção de assinaturas recorrentes e alertas de orçamento por e-mail/Telegram.
- Webhooks da Pluggy (`item/updated`) para sincronizar em tempo real.
