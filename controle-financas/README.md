# 💰 Controle de Finanças com Open Finance

Registra **automaticamente todos os seus gastos e investimentos** puxando os dados
das suas contas, cartões e corretoras pelo **Open Finance Brasil**, guarda tudo num
banco SQLite local e gera relatórios por categoria, orçamentos mensais, carteira de
investimentos e evolução do patrimônio.

> 📘 **Primeira vez? Siga o [GUIA.md](GUIA.md)** — passo a passo completo, do
> zero (instalar Python) até a sincronização automática diária.

> Pessoa física não acessa as APIs do Open Finance diretamente — é preciso uma
> instituição autorizada. Este projeto usa a **[Pluggy](https://pluggy.ai)**, que
> tem plano gratuito para desenvolvimento.

## 1. Instalação
```bash
cd controle-financas
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

## 2. Teste sem banco real
```bash
python -m financas sincronizar --fake
python -m financas resumo
```

## 3. Conectar ao seu Open Finance (Pluggy)
1. Crie conta em <https://dashboard.pluggy.ai> e crie uma **Application**;
   copie o `Client ID` e o `Client Secret` para o `.env`.
2. Conecte seus bancos: no dashboard, use o fluxo de conexão (Pluggy Connect /
   conector **MeuPluggy**, que usa o consentimento oficial do Open Finance —
   você autoriza dentro do app do seu banco).
3. Cada conexão gera um **Item ID**. Coloque-os em `PLUGGY_ITEM_IDS`
   (separados por vírgula) e mude `FINANCAS_PROVEDOR=pluggy`.
4. Rode `python -m financas sincronizar`.

> Os passos do dashboard podem mudar; confira a documentação oficial em
> <https://docs.pluggy.ai>. Consentimentos do Open Finance expiram (até 12 meses)
> e precisam ser renovados.

## 4. Comandos
| Comando | O que faz |
|---|---|
| `diagnostico` | Confere o `.env` e a conexão com a Pluggy |
| `sincronizar [--desde AAAA-MM-DD] [--fake]` | Baixa transações e investimentos (incremental) |
| `contas` | Lista contas e saldos |
| `gastos [--mes AAAA-MM] [--categoria X] [--busca txt] [--todos]` | Lista gastos |
| `resumo [--mes AAAA-MM]` | Receitas, gastos, saldo e % por categoria |
| `categorizar <id> <categoria>` | Corrige a categoria de uma transação |
| `regra adicionar "<texto>" <categoria>` / `regra listar` / `regra remover <id>` | Regras automáticas |
| `orcamento definir <categoria> <valor>` / `orcamento listar` | Limites mensais |
| `recategorizar` | Reaplica regras a todo o histórico |
| `exportar arquivo.csv [--mes AAAA-MM]` | Exporta para Excel/Sheets |
| `investimentos` | Carteira por tipo, com rendimento |
| `investimento adicionar "<nome>" --tipo X --saldo V [--aplicado V]` | Cadastra investimento fora do Open Finance (cripto, exterior…) |
| `investimento atualizar <id> --saldo V` / `investimento remover <id>` | Mantém os manuais |
| `patrimonio` | Contas + investimentos − cartões, e evolução mensal |

Exemplo:
```bash
python -m financas regra adicionar "ifood" Alimentação
python -m financas orcamento definir Alimentação 800
python -m financas resumo --mes 2026-11
```

## 5. Sincronizar todo dia
Use `scripts/sincronizar.bat` (Windows, Agendador de Tarefas) ou
`scripts/sincronizar.sh` (cron). Detalhes na seção 14 do [GUIA.md](GUIA.md).

## 6. Usando com o Claude no VS Code
Abra a pasta `controle-financas` no VS Code com a extensão do Claude Code.
O arquivo `CLAUDE.md` explica a arquitetura e as regras do projeto para o Claude.
Peça, por exemplo:
- "Crie um dashboard em Streamlit com gráfico de gastos por categoria"
- "Adicione detecção de assinaturas recorrentes"
- "Mande um alerta no Telegram quando um orçamento estourar"

## Segurança
`.env`, `*.db`, `*.csv` e `*.log` ficam fora do git. Seus dados ficam só na sua máquina.
O acesso é somente leitura.
