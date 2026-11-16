# Guia passo a passo — Controle de Finanças com Open Finance

Este guia leva você do zero até ter **todos os seus gastos e investimentos**
registrados automaticamente, rodando no seu computador e editável com o Claude
no VS Code. Leia na ordem; cada etapa termina com um **✅ Confira** para você
saber que deu certo antes de seguir.

> Os comandos aparecem para **Windows (PowerShell)** e para **macOS/Linux
> (Terminal)**. Quando só houver uma versão, ela serve para os dois.

---

## Sumário
1. [Entenda como funciona](#1-entenda-como-funciona)
2. [Instale o Python](#2-instale-o-python)
3. [Instale o Git](#3-instale-o-git)
4. [Instale o VS Code e o Claude Code](#4-instale-o-vs-code-e-o-claude-code)
5. [Baixe o projeto](#5-baixe-o-projeto)
6. [Crie o ambiente virtual e instale as dependências](#6-crie-o-ambiente-virtual-e-instale-as-dependências)
7. [Teste com dados fictícios](#7-teste-com-dados-fictícios)
8. [Crie sua conta na Pluggy](#8-crie-sua-conta-na-pluggy)
9. [Conecte seus bancos pelo Open Finance](#9-conecte-seus-bancos-pelo-open-finance)
10. [Configure o arquivo .env](#10-configure-o-arquivo-env)
11. [Primeira sincronização real](#11-primeira-sincronização-real)
12. [Investimentos](#12-investimentos)
13. [Uso no dia a dia](#13-uso-no-dia-a-dia)
14. [Sincronização automática todo dia](#14-sincronização-automática-todo-dia)
15. [Evoluindo o projeto com o Claude no VS Code](#15-evoluindo-o-projeto-com-o-claude-no-vs-code)
16. [Problemas comuns](#16-problemas-comuns)
17. [Segurança e privacidade](#17-segurança-e-privacidade)

---

## 1. Entenda como funciona

```
 Seu banco / corretora ──(Open Finance, com seu consentimento)──► Pluggy
                                                                    │ API
                                                                    ▼
                               python -m financas sincronizar  (seu computador)
                                                                    │
                                                                    ▼
                                        financas.db (SQLite, só na sua máquina)
                                                                    │
                                     resumo · gastos · investimentos · patrimônio
```

- **Open Finance Brasil** é o sistema regulado pelo Banco Central que permite
  compartilhar seus dados bancários com sua autorização.
- Pessoa física **não acessa a API do Open Finance diretamente** — só
  instituições autorizadas. Por isso usamos a **Pluggy**, uma empresa que já é
  autorizada e expõe esses dados numa API simples.
- O acesso é **somente leitura**: o programa não consegue mover dinheiro.
- O que é sincronizado: **contas, saldos, transações (conta e cartão) e
  investimentos**.

**Tempo estimado:** 40–60 minutos na primeira vez.

---

## 2. Instale o Python

### Windows
1. Acesse <https://www.python.org/downloads/> e clique em **Download Python 3.x**
   (use 3.10 ou mais novo).
2. Abra o instalador. **Marque a caixa "Add python.exe to PATH"** na primeira
   tela (muito importante!).
3. Clique em **Install Now** e aguarde.

### macOS
1. Baixe o instalador em <https://www.python.org/downloads/> e instale,
   **ou** com Homebrew: `brew install python`.

### Linux (Ubuntu/Debian)
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

### ✅ Confira
Abra um terminal **novo** (no Windows: menu Iniciar → "PowerShell") e rode:
```bash
python --version      # Windows
python3 --version     # macOS/Linux
```
Deve aparecer algo como `Python 3.12.x`.

> Daqui em diante, no macOS/Linux use `python3` onde o guia disser `python`
> **até ativar o ambiente virtual** (etapa 6). Depois dele, `python` funciona.

---

## 3. Instale o Git

- **Windows:** baixe em <https://git-scm.com/download/win> e instale com as
  opções padrão (pode ir clicando em *Next*).
- **macOS:** rode `git --version`; se não tiver, o sistema oferece instalar.
- **Linux:** `sudo apt install -y git`

### ✅ Confira
```bash
git --version
```

---

## 4. Instale o VS Code e o Claude Code

1. Baixe e instale o VS Code: <https://code.visualstudio.com/>.
2. Abra o VS Code → clique no ícone de **Extensões** na barra lateral
   (quadradinhos) ou `Ctrl+Shift+X` (`Cmd+Shift+X` no Mac).
3. Procure **"Claude Code"** (publicada pela **Anthropic**) e clique em
   **Install**.
4. Instale também a extensão **"Python"** (da Microsoft).
5. Clique no ícone do Claude que aparece na barra lateral/superior e faça login
   com a sua conta Claude.

### ✅ Confira
O painel do Claude abre e aceita mensagens.

---

## 5. Baixe o projeto

1. Escolha uma pasta para seus projetos, por exemplo `Documentos`.
2. Abra o terminal nessa pasta e rode:

```bash
git clone https://github.com/spatrek1/Projetos-Python.git
cd Projetos-Python
git checkout claude/cool-franklin-egn0ed
```

> O último comando seleciona a *branch* onde o projeto está. Se você já
> tiver feito *merge* dela na `main`, pode pular esse comando.

3. No VS Code: **File → Open Folder…** e abra a pasta
   `Projetos-Python/controle-financas`.
4. Abra o terminal integrado do VS Code: **Terminal → New Terminal**
   (`` Ctrl+` ``). Todos os próximos comandos são executados nele.

### ✅ Confira
```bash
dir        # Windows
ls         # macOS/Linux
```
Você deve ver `financas`, `tests`, `README.md`, `GUIA.md`, `requirements.txt`…

---

## 6. Crie o ambiente virtual e instale as dependências

O ambiente virtual (`.venv`) isola as bibliotecas deste projeto.

### Windows (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
Se aparecer erro dizendo que **a execução de scripts está desabilitada**, rode
uma única vez:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
e repita o `Activate.ps1`.

### macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Agora instale as bibliotecas:
```bash
pip install -r requirements.txt
```

Por fim, diga ao VS Code para usar esse Python: `Ctrl+Shift+P` →
**"Python: Select Interpreter"** → escolha o que tem `.venv` no caminho.

### ✅ Confira
- O início da linha do terminal mostra `(.venv)`.
- Rode os testes:
  ```bash
  python -m pytest -q
  ```
  Deve terminar com algo como `19 passed`.

> **Toda vez** que abrir um terminal novo, ative o ambiente de novo
> (`.venv\Scripts\Activate.ps1` ou `source .venv/bin/activate`). O VS Code
> costuma fazer isso sozinho depois que você seleciona o interpretador.

---

## 7. Teste com dados fictícios

Antes de mexer com dados reais, veja tudo funcionando com dados de mentira:

```bash
python -m financas sincronizar --fake
python -m financas resumo
python -m financas gastos --limite 10
python -m financas investimentos
python -m financas patrimonio
```

### ✅ Confira
Aparecem um resumo do mês, uma lista de gastos e uma carteira com CDB,
Tesouro, fundo e ação fictícios.

### ⚠️ Apague os dados de teste
Para não misturar dados fictícios com os reais, apague o banco de teste:
```powershell
del financas.db       # Windows
```
```bash
rm financas.db        # macOS/Linux
```

---

## 8. Crie sua conta na Pluggy

1. Acesse <https://dashboard.pluggy.ai> e clique em **Sign up / Criar conta**.
   Confirme o e-mail.
2. No dashboard, crie uma **aplicação** (botão do tipo *"Nova aplicação"* /
   *"Create application"*). Dê um nome, por exemplo `controle-financas`.
3. Abra a aplicação e localize as credenciais:
   - **Client ID**
   - **Client Secret** (às vezes é preciso clicar em "mostrar"/"gerar")
4. Guarde os dois — você vai colá-los no `.env` na etapa 10.
   **Não compartilhe o Client Secret com ninguém** (nem cole em chats).

> A Pluggy pode mudar nomes de botões e condições de planos. Confira os planos
> disponíveis (há opções de teste/desenvolvimento) e a documentação oficial em
> <https://docs.pluggy.ai>.

### ✅ Confira
Você tem um Client ID e um Client Secret anotados num lugar seguro.

---

## 9. Conecte seus bancos pelo Open Finance

Cada banco/corretora conectado vira um **Item** na Pluggy, com um **Item ID**.
Para uso pessoal, o caminho mais simples é o **Meu Pluggy**:

### 9.1 Conectar os bancos no Meu Pluggy
1. Acesse <https://meu.pluggy.ai> e crie sua conta.
2. Clique para **adicionar uma conexão** e escolha seu banco.
3. Você será redirecionado para o **app ou site do seu banco** — este é o
   consentimento oficial do Open Finance.
4. No banco, revise e **autorize** o compartilhamento. Marque todas as
   categorias de dados que quiser trazer, principalmente:
   - Contas e saldos
   - Cartão de crédito
   - **Investimentos** (necessário para a etapa 12)
   - Prazo: escolha o maior disponível (normalmente **12 meses**).
5. Volte ao Meu Pluggy e aguarde a conexão ficar com status de sucesso.
6. Repita para cada banco/corretora (Nubank, Itaú, Inter, XP, BTG…).

### 9.2 Levar as conexões para a sua aplicação
> ⚠️ Os IDs que aparecem no **meu.pluggy.ai** (em "Ver detalhes" ou no link
> `meu.pluggy.ai/connections/...`) **não funcionam** no programa — a Pluggy
> responde "item not found". Só valem os IDs criados pelo **dashboard**.

1. No **dashboard da Pluggy**, vá em **Dados Financeiros → Customização** e
   adicione o conector **MeuPluggy** à lista de conectores.
2. Em **Visão Geral → "Conecte um item demo" → Conectar**, escolha
   **MeuPluggy** e faça login com a conta criada no passo 9.1.
3. Autorize **um banco por vez** (repita para cada banco/corretora).
4. Copie o **Item ID** de cada conexão (um texto longo no formato
   `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).

> **Custo:** o dashboard mostra um "trial de 15 dias", mas segundo o
> [README oficial do MeuPluggy](https://github.com/pluggyai/meu-pluggy) você
> continua puxando seus dados depois que ele expira. Não é preciso clicar em
> "Liberar dados reais" nem contratar plano. Os dados atualizam 1x por dia.

> Se a interface estiver diferente, procure na documentação da Pluggy por
> "Meu Pluggy" ou "Pluggy Connect". O que importa é terminar com **um ou mais
> Item IDs** ligados à **sua** aplicação (mesmo Client ID).
>
> Alternativa: conectar cada banco direto pelo conector Open Finance dele no
> Pluggy Connect — também gera um Item ID por banco.

### ✅ Confira
Você tem uma lista de Item IDs, um por conexão.

---

## 10. Configure o arquivo .env

O `.env` guarda suas configurações e segredos. Ele **nunca** vai para o Git
(já está no `.gitignore`).

1. Crie o arquivo a partir do modelo:
   ```powershell
   copy .env.example .env     # Windows
   ```
   ```bash
   cp .env.example .env       # macOS/Linux
   ```
2. Abra o `.env` no VS Code e preencha:

```ini
FINANCAS_PROVEDOR=pluggy

PLUGGY_CLIENT_ID=cole-aqui-o-client-id
PLUGGY_CLIENT_SECRET=cole-aqui-o-client-secret

# Vários Item IDs separados por vírgula, sem espaços:
PLUGGY_ITEM_IDS=1111aaaa-...,2222bbbb-...

FINANCAS_DB=financas.db

# Quantos dias de histórico buscar na primeira vez
FINANCAS_DIAS_INICIAIS=365
```

3. Salve (`Ctrl+S`).

### ✅ Confira
```bash
python -m financas diagnostico
```
Resultado esperado:
```
Provedor configurado: pluggy
Client ID preenchido: sim
Client Secret:        preenchido
Items configurados:   2
Autenticação na Pluggy: OK
  item 1111aaaa-...: 2 conta(s), 5 investimento(s)
     - Conta Corrente (BANK)
     - Cartão Platinum (CREDIT)
Tudo certo! Agora rode: python -m financas sincronizar
```
Se der erro, veja [Problemas comuns](#16-problemas-comuns).

---

## 11. Primeira sincronização real

```bash
python -m financas sincronizar
```

A primeira vez busca os últimos `FINANCAS_DIAS_INICIAIS` dias (pode demorar
um pouco). Depois disso, cada sincronização busca só o que é novo (e revisa
os últimos 7 dias, porque compras pendentes mudam de status).

> O histórico disponível depende do banco. Algumas instituições só liberam
> 90 dias ou 12 meses pelo Open Finance.

### ✅ Confira
```bash
python -m financas contas
python -m financas resumo
python -m financas gastos --limite 20
```

---

## 12. Investimentos

### 12.1 Investimentos que vêm pelo Open Finance
Se você autorizou a categoria **Investimentos** no consentimento, cada
`sincronizar` traz automaticamente suas posições: **renda fixa** (CDB, LCI,
LCA, Tesouro, debêntures…), **fundos**, **ações**, **ETFs**, **previdência**
e **COE** — conforme o que cada instituição disponibiliza.

```bash
python -m financas investimentos
```
Mostra a carteira agrupada por tipo, o valor atual (líquido), a % de cada
tipo, a taxa/indexador, o vencimento e o **rendimento** quando a instituição
informa o valor aplicado.

```bash
python -m financas patrimonio
```
Mostra **contas + investimentos − faturas de cartão** = patrimônio líquido, e
a **evolução mês a mês** dos investimentos (o programa guarda uma "foto" por
dia a cada sincronização — quanto mais você sincroniza, melhor o histórico).

Quando um investimento some do banco (resgate/vencimento), ele é marcado como
**inativo** e sai do total, mas o histórico continua guardado.

### 12.2 Investimentos que NÃO vêm pelo Open Finance
Cripto, contas no exterior, previdência de empresa, um CDB num banco sem
Open Finance… cadastre manualmente:

```bash
python -m financas investimento adicionar "Bitcoin" --tipo CRYPTO --saldo 4200 --aplicado 3000 --instituicao Binance

python -m financas investimento adicionar "CDB Banco X 2027" --tipo FIXED_INCOME --subtipo CDB --saldo 10500 --aplicado 10000 --taxa "120% CDI" --vencimento 2027-03-10
```

Tipos aceitos em `--tipo`: `FIXED_INCOME` (renda fixa), `MUTUAL_FUND`
(fundos), `EQUITY` (ações), `ETF`, `SECURITY` (previdência), `COE`,
`CRYPTO`, `OTHER`.

O comando mostra o ID (ex.: `manual-2bd2e5dd`). Uma vez por mês, atualize o
valor:
```bash
python -m financas investimento atualizar manual-2bd2e5dd --saldo 4550
```
Para apagar:
```bash
python -m financas investimento remover manual-2bd2e5dd
```

### ✅ Confira
`python -m financas investimentos` mostra seus investimentos reais e os
manuais (marcados como `manual`).

---

## 13. Uso no dia a dia

### Comandos principais
| Comando | Para quê |
|---|---|
| `python -m financas sincronizar` | Baixa tudo o que é novo |
| `python -m financas resumo --mes 2026-11` | Receitas, gastos, saldo e % por categoria |
| `python -m financas gastos --mes 2026-11` | Lista gastos do mês |
| `python -m financas gastos --categoria Mercado` | Filtra por categoria |
| `python -m financas gastos --busca uber` | Busca na descrição |
| `python -m financas gastos --todos` | Inclui receitas |
| `python -m financas investimentos` | Carteira de investimentos |
| `python -m financas patrimonio` | Patrimônio líquido e evolução |
| `python -m financas contas` | Contas e saldos |
| `python -m financas exportar novembro.csv --mes 2026-11` | Planilha (abre no Excel) |
| `python -m financas <comando> --help` | Ajuda de qualquer comando |

### Arrumando as categorias
Os gastos são categorizados automaticamente. Para melhorar:

1. **Regras** (valem para todas as transações, passadas e futuras):
   ```bash
   python -m financas regra adicionar "ifood" Alimentação
   python -m financas regra adicionar "academia smart" Saúde
   python -m financas regra listar
   python -m financas regra remover 2
   ```
   A regra procura o texto dentro da descrição (sem diferenciar maiúsculas
   nem acentos).
2. **Correção manual** de uma transação específica (o ID aparece entre
   colchetes no comando `gastos`):
   ```bash
   python -m financas categorizar <id-da-transacao> Presentes
   ```
   Correções manuais nunca são sobrescritas.

### Orçamentos
```bash
python -m financas orcamento definir Alimentação 800
python -m financas orcamento definir Lazer 400
python -m financas orcamento listar
```
O `resumo` mostra quanto de cada orçamento já foi usado e avisa
**⚠ ESTOUROU** quando passar do limite.

### Rotina sugerida
- **Toda semana:** `resumo` → veja se algum orçamento está perto do limite.
- **Todo mês:** crie regras para o que caiu em "Outros", atualize os
  investimentos manuais e rode `patrimonio`.

---

## 14. Sincronização automática todo dia

### Windows — Agendador de Tarefas
1. Menu Iniciar → **Agendador de Tarefas** → **Criar Tarefa Básica…**
2. Nome: `Sincronizar finanças` → Avançar.
3. Disparador: **Diariamente**, horário ex.: `08:00`.
4. Ação: **Iniciar um programa**.
5. Programa/script: clique em *Procurar* e escolha
   `controle-financas\scripts\sincronizar.bat`.
6. Concluir. Para testar, clique com o botão direito na tarefa → **Executar**.
7. O resultado fica em `controle-financas\sincronizacao.log`.

### macOS/Linux — cron
```bash
crontab -e
```
Adicione a linha (troque o caminho pelo seu):
```
0 8 * * * /caminho/para/Projetos-Python/controle-financas/scripts/sincronizar.sh
```
O resultado fica em `sincronizacao.log`.

---

## 15. Evoluindo o projeto com o Claude no VS Code

O arquivo `CLAUDE.md` explica para o Claude como o projeto é organizado e
quais regras seguir (valores em centavos, testes sem internet, nunca expor o
`.env`…). Então você pode pedir mudanças em linguagem natural.

1. Abra a pasta `controle-financas` no VS Code.
2. Abra o painel do Claude Code.
3. Peça, por exemplo:
   - *"Crie um dashboard em Streamlit com gráfico de gastos por categoria e
     evolução do patrimônio."*
   - *"Adicione um comando que detecta assinaturas recorrentes."*
   - *"Mande um alerta no Telegram quando um orçamento estourar."*
   - *"Mostre a rentabilidade da carteira comparada com o CDI."*
   - *"Explique como funciona o arquivo sync.py."*
4. Revise o que o Claude propõe, aceite as mudanças e peça para ele rodar os
   testes (`python -m pytest -q`).

**Dicas**
- Peça uma coisa por vez e teste antes de pedir a próxima.
- Nunca cole o conteúdo do `.env` no chat.
- Use o Git para salvar versões: `git add . && git commit -m "descrição"`.

---

## 16. Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `'python' não é reconhecido` | Python fora do PATH | Reinstale marcando **Add python.exe to PATH**, ou use `py` no lugar de `python` |
| `execução de scripts foi desabilitada` | Política do PowerShell | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `No module named requests` / `financas` | Ambiente virtual não ativado, ou terminal fora da pasta `controle-financas` | Ative o `.venv` e entre na pasta |
| `Defina PLUGGY_CLIENT_ID...` | `.env` vazio ou fora da pasta | Confira se o `.env` está em `controle-financas/` e foi salvo |
| `Falha na autenticação Pluggy (401/403)` | Client ID/Secret errados | Copie de novo do dashboard, sem espaços nem aspas |
| `GET /accounts falhou (404)` | Item ID errado ou de outra aplicação | Copie o Item ID da lista de Items **da mesma aplicação** |
| Sincroniza mas vem 0 investimentos | Consentimento sem "Investimentos", ou instituição não envia | Refaça o consentimento marcando Investimentos; cadastre manualmente o que faltar |
| Transações pararam de chegar | Consentimento expirou (máx. 12 meses) ou conexão com erro | Renove a conexão no Meu Pluggy / no banco |
| Dados fictícios misturados | Esqueceu de apagar o `financas.db` de teste | Apague `financas.db` e rode `sincronizar` de novo |

---

## 17. Segurança e privacidade

- Seus dados ficam **apenas no seu computador** (`financas.db`). O `.env`,
  `*.db`, `*.csv` e `*.log` estão no `.gitignore` — **não remova** essas
  linhas e não envie esses arquivos para o GitHub.
- O **Client Secret** dá acesso aos seus dados bancários: trate como senha.
  Se vazar, gere um novo no dashboard da Pluggy.
- O acesso é **somente leitura**; o programa não faz pagamentos nem PIX.
- Você pode **revogar o consentimento** a qualquer momento no app do seu
  banco (área de Open Finance) ou no Meu Pluggy.
- Faça backup do `financas.db` de vez em quando (copie para um pendrive ou
  pasta criptografada).
