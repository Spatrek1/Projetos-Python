# App Android — Finanças

App de celular que **sincroniza sozinho com a Pluggy** e mostra resumo do mês,
gastos, investimentos e patrimônio. Usa o mesmo código do programa do PC
(pasta `financas/`) e guarda os dados **só no celular**.

| Aba | O que mostra |
|---|---|
| **Resumo** | Receitas, gastos e saldo do mês, % por categoria, alerta de orçamento e o que ficou "fora do total" |
| **Gastos** | Lançamentos do mês, com filtro por categoria |
| **Invest.** | Carteira por grupo (Ações, FIIs, Renda fixa…), com rendimento, taxa e vencimento |
| **Patrimônio** | Contas + investimentos − faturas, saldos de cada conta e evolução mês a mês |
| **Ajustes** | Chaves da Pluggy, botão de sincronizar e regras de categoria |

---

## 1. Gerar o APK (no PC)

Precisa: Python 3.13 e o ambiente virtual do projeto (`.venv`). O Briefcase baixa
sozinho o Java 17 e o Android SDK na primeira vez (alguns GB, demora).

> ⚠️ **O caminho das ferramentas não pode ter espaço.** Como a pasta do seu
> usuário do Windows tem espaço, defina `BRIEFCASE_HOME` antes de rodar.

```powershell
cd C:\Documentos\Projetos-Python-financas\controle-financas
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
$env:BRIEFCASE_HOME = "C:\Documentos\briefcase-home"

.\.venv\Scripts\briefcase.exe create android    # só na 1ª vez
.\.venv\Scripts\briefcase.exe build android
```

O APK fica em:
```
build\financasapp\android\gradle\app\build\outputs\apk\debug\app-debug.apk
```

Depois de mudar o código, gere de novo com:
```powershell
.\.venv\Scripts\briefcase.exe update android
.\.venv\Scripts\briefcase.exe build android
```

### ✅ Confira
O comando termina mostrando o caminho do `app-debug.apk`.

---

## 2. Instalar no celular

**Opção A, sem cabo:** mande o `app-debug.apk` para você mesmo (Google Drive,
e-mail ou WhatsApp "Mensagem para mim"), abra o arquivo no celular e toque em
**Instalar**. O Android vai pedir para **permitir instalar apps desta fonte**:
permita só para o app que você usou para abrir o arquivo.

**Opção B, com cabo USB:** ative as *Opções do desenvolvedor* → *Depuração USB*
no celular, ligue o cabo e rode:
```powershell
.\.venv\Scripts\briefcase.exe run android
```

> O Play Protect pode avisar que o app é "desconhecido". É normal para um APK
> que você mesmo gerou e não está na Play Store: toque em **Instalar assim mesmo**.

### ✅ Confira
O ícone **Finanças** aparece no celular e o app abre na aba Resumo dizendo
"Nenhum dado ainda".

---

## 3. Configurar no celular

1. Abra a aba **Ajustes**.
2. Preencha **Client ID**, **Client Secret** e os **Item IDs** (um por linha).
   São os mesmos valores do `.env` do PC.
3. Toque em **Salvar** e depois em **Sincronizar agora**.
4. A primeira sincronização baixa 12 meses e pode levar alguns minutos.

As **regras de categoria** do PC não vão junto (cada lugar tem o seu banco de
dados). Recrie as que quiser em **Ajustes → Regras de categoria**. Lembre que
vence a primeira regra da lista: a do CNPJ do MEI precisa vir antes da do seu nome.

### ✅ Confira
A mensagem "Sincronizado: 9 conta(s)…" aparece e as abas mostram seus dados.

---

## Segurança

- As chaves ficam num arquivo na **área privada do app**, que outros apps não
  conseguem ler. Mesmo assim, use **bloqueio de tela** no celular.
- Se perder o celular, **gere um Client Secret novo** no dashboard da Pluggy:
  a chave antiga para de funcionar na hora.
- O app só **lê** dados (não faz pagamentos nem transferências).
- O APK **não contém** suas chaves nem seus dados: pode gerar e reinstalar
  sem medo. Desinstalar o app apaga os dados do celular.

## Problemas comuns

| Problema | Causa provável | Solução |
|---|---|---|
| `contains spaces` ao rodar o Briefcase | Pasta do usuário com espaço | Defina `BRIEFCASE_HOME` como no passo 1 |
| "Erro ao sincronizar: ... 404 ... item not found" | Item ID copiado do meu.pluggy.ai | Use os IDs do dashboard (veja GUIA.md, etapa 9.2) |
| "Erro ao sincronizar: Falha na autenticação" | Client ID/Secret errado ou trocado | Confira e salve de novo em Ajustes |
| Celular bloqueia a instalação | Fonte desconhecida | Permita instalar a partir do app que abriu o APK |
