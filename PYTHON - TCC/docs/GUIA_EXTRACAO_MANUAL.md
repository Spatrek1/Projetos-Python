# Guia de obtenção dos dados do IF.data

Procedimento completo para obter os dados do IF.data/COSIF e prepará-los para o
pipeline, pelas **duas rotas possíveis**: coleta automática via API (seção 0) e
extração manual pela interface web (seções 1 a 5). As duas convergem na seção 6
— dali em diante o tratamento é idêntico.

O documento é mais detalhado na rota manual porque é a que exige procedimento
humano repetitivo e sujeito a erro silencioso. A rota automática está descrita
na seção 0 e detalhada em `DOCUMENTACAO_MODULOS.md`, seção 2.

> **Nota sobre este guia.** Ele foi escrito sem acesso ao site do Banco Central
> (o ambiente de desenvolvimento tinha `bcb.gov.br` bloqueado). Os passos
> descrevem o *fluxo* da extração e o que procurar em cada tela; rótulos exatos
> de botão e nomes de relatório devem ser confirmados por você na interface.
> Onde há incerteza, o texto diz explicitamente **confirme na tela**.

---

## Sumário

0. [As duas rotas: automática e manual](#0)
1. [Por que a extração manual não é um plano B inferior](#1)
2. [O que precisa ser baixado](#2)
3. [Passo a passo da extração](#3)
4. [Convenção de nomes dos arquivos](#4)
5. [Validação da extração](#5)
6. [Carregamento no pipeline](#6)
7. [Tratamento: do CSV bruto ao painel](#7)
8. [Registro para reprodutibilidade](#8)
9. [Problemas frequentes](#9)

---

<a id="0"></a>
## 0. As duas rotas: automática e manual

Existem dois caminhos para obter os mesmos dados. **Eles convergem na seção 6**
— dali em diante, o pipeline é idêntico.

```
ROTA A (automática)                      ROTA B (manual)
API OData do IF.data                     Interface web do IF.data
        │                                        │
  notebook §2: descoberta                  download CSV por trimestre
  notebook §2.1: RELATORIOS                nomear com AAAAMM
  notebook §3.1: coleta                    validar_extracao_manual.py
        │                                        │
        └──────────────┬─────────────────────────┘
                       ↓
              notebook §3.3 (formato longo → largo)
              §4 segmentação · §5 mapeamento · §6 indicadores
```

### Qual escolher

| Situação | Rota |
|---|---|
| API responde e as consultas retornam dados | **A** — muito mais rápido |
| API responde mas as consultas falham | **A**, depois de ajustar (ver 0.2) |
| API bloqueada por rede corporativa | **B** |
| Precisa anexar arquivos-fonte ao TCC | **B**, ou A **e** B (recomendado) |

### 0.1 Rota A — passo a passo

**1. Confirme o acesso**

```powershell
python testes\diagnostico_rede.py
```

Precisa terminar com `SUCESSO`. Se não terminar, a mensagem indica o que
corrigir; se for bloqueio de política, vá para a Rota B.

**2. Descubra o esquema — notebook, seção 2**

Esta célula é o coração da rota automática:

```python
cliente = ifdata.ClienteIFData()
catalogo_servico = cliente.descrever_servico()
```

Ela baixa o documento `$metadata`, interpreta o XML e imprime uma tabela com os
recursos que o serviço **realmente** publica: nome, parâmetros exigidos e
campos disponíveis.

**Leia essa tabela antes de qualquer outra coisa.** Nada no código presume o
contrato da API — é essa saída que informa quais códigos de relatório e de tipo
de instituição existem.

**3. Preencha os códigos — notebook, seção 2.1**

```python
RELATORIOS = ["1", "2", "4"]      # confirmar na tabela da seção 2
TIPOS_INSTITUICAO = [2]           # confirmar na tabela da seção 2
```

Enquanto estiverem vazios, o pipeline registra pendência bloqueante — de
propósito, para que ninguém rode a coleta no escuro.

**4. Colete — notebook, seção 3.1**

```python
bruto_longo = cliente.coletar_painel(RELATORIOS, TIPOS_INSTITUICAO)
```

Varre período × relatório × tipo. Falhas isoladas **não** interrompem a
varredura: são registradas e o período fica ausente, o que a seção 16 reporta.
Cada resposta é gravada em `dados/brutos/` com carimbo de data.

**5. Anote a data de coleta**

```python
print(bruto_longo.attrs["coletado_em"])
```

Vai para o TCC. O IF.data republica períodos quando há reapresentação de
documento.

### 0.2 Rota A — quando as consultas falham

O `$metadata` responder não garante que as consultas de valores funcionem. Erros
típicos e o que fazer:

| Sintoma | Causa provável | Correção |
|---|---|---|
| `HTTP 400` na consulta de valores | Parâmetro com nome ou tipo diferente do esperado | Rode `cliente.descrever_servico()` e confira a coluna `parametros` do recurso `IfDataValores` |
| `HTTP 404` no recurso | Nome do recurso mudou | Ajuste `recursos_candidatos` em `config.py` (`ConfigColeta`) |
| Retorno vazio, sem erro | Combinação período/relatório/tipo não existe | Teste um período isolado: `cliente.valores(202403, rel, tipo)` |
| `KeyError` na pivotagem (§3.3) | Nomes de coluna presumidos | Ajuste `COL_INST`, `COL_CONTA`, `COL_VALOR` aos nomes reais |
| Coleta demora demais | 24 períodos × N relatórios × M tipos | Normal. O cache evita repetir na segunda execução |

**Teste isolado antes de varrer tudo.** Vale mais que depurar a varredura
completa:

```python
teste = cliente.valores(anomes=202403, relatorio="1", tipo_instituicao=2)
print(teste.shape)
print(teste.columns.tolist())
print(teste.head())
```

Se isso funcionar, a varredura funciona. Se não, a mensagem de erro dirá qual
parâmetro está errado — e o cliente foi escrito para não repetir erros 4xx,
justamente porque repetir não resolve nome inexistente.

**Quando desistir da Rota A.** Se depois de conferir o esquema e testar um
período isolado a consulta continuar falhando, não insista: o custo de depurar
um contrato de API não documentado supera o de baixar 24 arquivos. Vá para a
Rota B — o resultado no TCC é o mesmo, e ainda ganha os arquivos-fonte
anexáveis.

### 0.3 O que vale para as duas rotas

Independentemente da rota escolhida, valem as seções 5 a 8 deste guia:
validação, carregamento, tratamento e registro de procedência. E vale a decisão
da seção 2.4 — **conglomerado prudencial ou instituição individual** — que
precisa ser tomada antes de coletar, nos dois caminhos.

---

<a id="1"></a>
## 1. Por que a extração manual não é um plano B inferior

A coleta via API é mais rápida, mas tem uma fragilidade que importa em trabalho
acadêmico: **o resultado depende de a API continuar no ar e continuar
respondendo igual**. O IF.data admite republicação de períodos anteriores
quando uma instituição reapresenta documento — duas coletas em datas diferentes
podem produzir painéis diferentes, e a banca não tem como verificar qual foi a
sua.

A extração manual inverte isso. Os arquivos ficam anexados ao trabalho, com
data de download registrada. Qualquer pessoa pode reproduzir o resultado a
partir deles, mesmo anos depois, sem depender do serviço.

O custo é o tempo: são 24 trimestres × número de relatórios. Contando com a
navegação, algo entre duas e quatro horas de trabalho repetitivo. Feito uma vez,
está feito para sempre.

**Recomendação:** mesmo que a API funcione, baixe os arquivos e anexe ao TCC.
Coleta automática para trabalhar, arquivos manuais para comprovar.

---

<a id="2"></a>
## 2. O que precisa ser baixado

### 2.1 Recorte

| Dimensão | Valor |
|---|---|
| Período | 2019 a 2024 |
| Datas-base | março, junho, setembro e dezembro de cada ano |
| Total | **24 trimestres** |
| Segmentos | S2 e S3 (o filtro é aplicado depois, no pipeline) |

Baixe **todas** as instituições de cada trimestre, não apenas as que você
imagina serem S2/S3. A classificação por segmento é feita no
`src/fraude_s2s3/segmentacao.py`, e filtrar antes traria dois riscos:
enquadrar errado por conta própria, e impedir a comparação com o restante do
sistema.

### 2.2 Conceitos exigidos e onde encontrá-los

O pipeline precisa de 26 conceitos contábeis, declarados em
`src/fraude_s2s3/mapeamento.py`. Seis são **obrigatórios** — sem eles nada roda:

| Conceito | Descrição | Onde costuma estar |
|---|---|---|
| `ativo_total` | Ativo total | Balanço patrimonial / Resumo |
| `carteira_credito` | Operações de crédito | Balanço patrimonial / Carteira de crédito |
| `provisao_pcld` | Provisão para créditos de liquidação duvidosa | Balanço / Carteira por nível de risco |
| `patrimonio_liquido` | Patrimônio líquido | Balanço patrimonial |
| `lucro_liquido` | Lucro líquido do período | Demonstração de resultado |
| `resultado_intermediacao` | Resultado bruto da intermediação financeira | Demonstração de resultado |

Os demais são opcionais, mas alguns carregam o núcleo da contribuição do
trabalho — sem eles, o estudo vira aplicação de modelo de empresa não
financeira a banco, que é exatamente o que ele se propõe a superar:

| Conceito | Por que importa |
|---|---|
| `carteira_eh` | Carteira classificada em níveis E–H (Res. CMN 2.682/1999). Base do teste de suficiência de provisão |
| `despesa_provisao` | Despesa de provisão do período. **Subprovisionar é o mecanismo mais direto de inflar resultado em banco** |
| `inadimplencia` | Permite detectar descasamento entre inadimplência e provisão |
| `creditos_tributarios` | Capital sustentado por lucro futuro; sinal de fragilidade |
| `indice_basileia` | Folga em relação ao mínimo regulatório |

### 2.3 Relatórios a procurar

Na interface do IF.data, os dados vêm organizados em relatórios. **Confirme os
nomes na tela** — costumam ser algo como:

- **Resumo** — visão consolidada; costuma trazer ativo, PL, lucro e Basileia
- **Balanço Patrimonial — Ativo** e **Passivo**
- **Demonstração de Resultado**
- **Carteira de crédito por nível de risco** — traz a classificação AA–H
- **Informações de capital** — Basileia, patrimônio de referência, RWA

**Um único relatório não cobre os conceitos obrigatórios.** No mínimo você
precisará de balanço, resultado e carteira por nível de risco.

### 2.4 Decisão que precisa ser tomada antes de baixar

O IF.data separa os dados por **tipo de instituição**. Os dois recortes
relevantes são:

| Recorte | Característica | Consequência |
|---|---|---|
| **Conglomerado prudencial** | Unidade sobre a qual incide o requerimento de capital e sobre a qual a Res. 4.553/2017 segmenta | Mais coerente com a definição de S2/S3; menos observações |
| **Instituição individual** | Cada CNPJ separadamente | Mais observações; risco de dupla contagem dentro de um mesmo grupo |

**Escolha um e mantenha em todo o recorte.** Misturar os dois duplica
instituições e contamina toda a comparação entre segmentos. Registre a escolha
na seção 3.2.1 do TCC.

Recomendação: **conglomerado prudencial**, por coerência com a norma de
segmentação. Confirme com seu orientador.

---

<a id="3"></a>
## 3. Passo a passo da extração

### Preparação

```powershell
cd "C:\Documentos\Projetos-Python\PYTHON - TCC"
mkdir dados\brutos\balanco
mkdir dados\brutos\resultado
mkdir dados\brutos\carteira
mkdir dados\brutos\capital
```

Uma subpasta por relatório. Isso facilita conferir cobertura por relatório e
evita confundir arquivos de origens diferentes.

### Ciclo de download

Para **cada um dos 24 trimestres**, repita:

1. Abra o IF.data no site do Banco Central
   *(seção Estabilidade Financeira → IF.data. **Confirme o caminho na tela.**)*

2. **Data-base**: selecione o trimestre (ex.: 03/2019)

3. **Tipo de instituição**: selecione o recorte escolhido na seção 2.4 —
   sempre o mesmo

4. **Relatório**: selecione o primeiro da sua lista

5. Clique em exportar / baixar CSV
   *(**confirme o rótulo do botão na tela** — pode ser um ícone de download)*

6. Renomeie conforme a seção 4 e mova para a subpasta correspondente

7. Repita os passos 4–6 para os demais relatórios do mesmo trimestre

8. Passe ao trimestre seguinte

### Sequência dos 24 trimestres

```
201903  201906  201909  201912
202003  202006  202009  202012
202103  202106  202109  202112
202203  202206  202209  202212
202303  202306  202309  202312
202403  202406  202409  202412
```

Sugestão prática: baixe **todos os trimestres de um relatório** antes de passar
ao próximo. Manter a mesma tela e mudar só a data-base reduz erro e é mais
rápido do que alternar entre relatórios.

---

<a id="4"></a>
## 4. Convenção de nomes dos arquivos

O carregador identifica o período **pelo nome do arquivo**. Sem período no
nome, a linha não entra no painel longitudinal.

```
<relatorio>_<AAAAMM>.csv
```

Exemplos válidos:

```
balanco_201903.csv
resultado_202412.csv
carteira_202106.csv
capital_2024-03.csv       (hífen aceito)
capital_2024_03.csv       (sublinhado aceito)
```

Inválidos:

```
ifdata (3).csv            sem período
balanco_marco_2019.csv    mês por extenso não é reconhecido
balanco_0319.csv          ano com dois dígitos
```

> **Atenção ao download do navegador.** Baixar vários arquivos do mesmo tipo
> gera `ifdata.csv`, `ifdata (1).csv`, `ifdata (2).csv`... Renomeie **logo
> após cada download**, antes de baixar o próximo. Renomear vinte arquivos
> depois, tentando lembrar a ordem, é fonte garantida de erro — e um trimestre
> trocado de lugar produz variação interanual falsa que ninguém detecta depois.

---

<a id="5"></a>
## 5. Validação da extração

Antes de qualquer modelagem:

```powershell
python testes\validar_extracao_manual.py dados\brutos\balanco
python testes\validar_extracao_manual.py dados\brutos\resultado
python testes\validar_extracao_manual.py dados\brutos\carteira
python testes\validar_extracao_manual.py dados\brutos\capital
```

O script confere cinco coisas:

| Verificação | O que detecta |
|---|---|
| **Cobertura** | Trimestres ausentes no recorte |
| **Duplicidade** | Mesmo período baixado mais de uma vez |
| **Formato** | Codificação, separador e decimal inconsistentes |
| **Colunas** | Rótulos que não se repetem entre arquivos |
| **Conceitos** | Quais dos 26 conceitos o material realmente cobre |

E imprime a **união dos rótulos de coluna encontrados** — insumo direto do
mapeamento contábil.

### Como ler o resultado

**`[FALTA]` em conceito obrigatório** → falta baixar um relatório. Volte à
seção 2.2 e identifique onde a conta está.

**`[?]` (ambíguo)** → mais de um rótulo casou com o mesmo conceito. Comum
quando existe "Ativo Total" e "Ativo Total Médio". Fixe a escolha certa:

```python
mapa = mapeamento.resolver(rotulos, preferencias={"ativo_total": "Ativo Total"})
```

**Trimestres ausentes** → o pipeline roda, mas a série fica incompleta. Os
indicadores de variação interanual (`delta_carteira`, `delta_roa`,
`sgi_bancario`) comparam um trimestre com o mesmo trimestre do ano anterior;
um buraco propaga por quatro trimestres.

**Formatos diferentes entre arquivos** → informe `sep` e `decimal`
explicitamente ao carregar. Inferência errada transforma número em texto sem
avisar, e o indicador vira `NaN` silencioso.

---

<a id="6"></a>
## 6. Carregamento no pipeline

No notebook, seção 3.2, substitua a coleta por API:

```python
bruto_longo = ifdata.carregar_csv_local(
    RAIZ / "dados" / "brutos" / "balanco",
    sep=";",           # confirme com a saída do validador
    decimal=",",
)
```

Para vários relatórios:

```python
import pandas as pd

partes = []
for pasta in ("balanco", "resultado", "carteira", "capital"):
    caminho = RAIZ / "dados" / "brutos" / pasta
    if caminho.exists():
        df = ifdata.carregar_csv_local(caminho, sep=";", decimal=",")
        df["relatorio"] = pasta
        partes.append(df)

bruto_longo = pd.concat(partes, ignore_index=True)
print(f"{len(bruto_longo):,} linhas de {len(partes)} relatório(s)")
```

O restante do notebook segue **sem nenhuma alteração**. O caminho manual e o
caminho por API convergem exatamente aqui.

---

<a id="7"></a>
## 7. Tratamento: do CSV bruto ao painel

Sequência aplicada pelo pipeline. Entender cada etapa importa porque cada uma
é uma decisão metodológica que a banca pode questionar.

### 7.1 Formato longo → formato largo

O IF.data entrega **formato longo**: uma linha por instituição × conta ×
período. Os modelos exigem **formato largo**: uma linha por instituição ×
período, com cada conta virando coluna.

```python
bruto_largo = (bruto_longo
    .pivot_table(index=["CodInst", "anomes"],
                 columns="NomeColuna",
                 values="Saldo",
                 aggfunc="first")
    .reset_index()
    .rename(columns={"CodInst": "cod_inst"}))
```

> Ajuste `CodInst`, `NomeColuna` e `Saldo` aos nomes reais que o validador
> mostrou. Esses três são apenas os mais prováveis.

`aggfunc="first"` é deliberado: se a mesma conta aparecer duas vezes para a
mesma instituição no mesmo período, algo está errado na extração — somar
mascararia o problema.

### 7.2 Conversão numérica

Valores brasileiros usam vírgula decimal e ponto de milhar. Se o `pandas`
inferir errado, `1.234.567,89` vira texto, e a coluna inteira vira `NaN` no
cálculo — **sem erro**. Por isso o `decimal=","` explícito.

Verifique depois de carregar:

```python
print(bruto_largo.dtypes.value_counts())
```

Colunas de valor devem ser `float64`. Se aparecerem como `object`, a conversão
falhou.

### 7.3 Segmentação S2/S3

Aplicada em `segmentacao.aplicar()`, com duas rotas:

1. **Lista oficial** (`dados/externos/segmentacao_oficial.csv`) — reproduz a
   classificação do supervisor
2. **Regra da norma** — Exposição/PIB, conforme Res. CMN 4.553/2017

A rota 2 é aproximação e **emite pendência bloqueante**: a norma considera
exposições fora do balanço e revisa o enquadramento em datas-base próprias.
Reconstruir por regra não é o mesmo que usar a classificação oficial.

### 7.4 Mapeamento contábil

`mapeamento.resolver()` casa os rótulos reais com os 26 conceitos, por padrões
de reconhecimento sobre o rótulo normalizado — sem acento, sem pontuação, sem
espaço. Ambiguidades são resolvidas por heurística **e reportadas**.

A tabela resultante é o *quadro de operacionalização das variáveis*: anexe-a
ao TCC.

### 7.5 Construção dos indicadores

`indicadores.construir()` produz 17 indicadores. Detalhamento completo em
`DOCUMENTACAO_MODULOS.md`, seção 6.

Indicador sem insumo é **omitido e reportado** — nunca preenchido com zero.

### 7.6 Tratamento do painel

| Etapa | O que faz | Por quê |
|---|---|---|
| Filtro de histórico | Exige ≥ 8 trimestres por instituição | Série curta não sustenta variação interanual |
| Descarte de esparsos | Remove indicador com > 40% de ausência | Coluna majoritariamente vazia é ruído |
| Winsorização | Corta caudas em 1% e 99%, **por trimestre** | Contas COSIF mudam de escala ao longo do período |
| Z-score por pares | Padroniza dentro de (segmento, trimestre), com mediana e MAD | A pergunta é "destoa dos pares agora?", não "destoa da população inteira" |
| Normalização | *Rank-gauss*, ajustada **só no treino** | Ajustar no conjunto todo é vazamento |
| Marcação de ausentes | Coluna-sombra `faltante_<x>` | Imputar a média faria ausência parecer normalidade |

### 7.7 Partição temporal

```
treino     2019-01 a 2022-12
validação  2023
teste      2024
```

Corte cronológico, **nunca aleatório**. Painel contábil é altamente persistente
dentro da instituição; divisão aleatória coloca trimestres futuros no treino e
o modelo passa a reconhecer a instituição em vez de generalizar.

---

<a id="8"></a>
## 8. Registro para reprodutibilidade

Anote e inclua no TCC:

| Item | Por quê |
|---|---|
| **Data de cada download** | O IF.data republica períodos quando há reapresentação |
| **Recorte escolhido** | Conglomerado prudencial ou instituição individual |
| **Relatórios baixados** | Nome exato como aparece na interface |
| **Trimestres ausentes** | Se houver, e a razão |
| **Preferências de mapeamento** | Ambiguidades resolvidas manualmente |

Modelo sugerido para `dados/brutos/PROCEDENCIA.md`:

```markdown
# Procedência dos dados

Fonte: IF.data — Banco Central do Brasil
Recorte: conglomerado prudencial
Período: 2019-03 a 2024-12 (24 trimestres)

| Relatório | Nome na interface | Downloads | Trimestres |
|---|---|---|---|
| balanco | Balanço Patrimonial - Ativo | 12/09/2026 | 24/24 |
| resultado | Demonstração de Resultado | 12/09/2026 | 24/24 |
| carteira | Carteira de crédito por nível de risco | 13/09/2026 | 22/24 |

Ausências: carteira 202409 e 202412 — não publicados na data da coleta.

Ambiguidades resolvidas:
- ativo_total -> "Ativo Total" (havia também "Ativo Total Médio")
```

---

<a id="9"></a>
## 9. Problemas frequentes

**Arquivo abre no Excel com tudo numa coluna só**
Separador é `;` e o Excel espera `,` (ou o contrário). Não corrija salvando pelo
Excel — ele reescreve o arquivo e pode alterar números. Informe o separador
correto ao carregar no Python.

**Acentos aparecem como `Ã§`, `Ã£`**
Codificação. O validador detecta e reporta; passe o `encoding` correto ao
`pandas`. Não é preciso reconverter o arquivo.

**O Excel transformou código de instituição em número**
Códigos com zero à esquerda perdem o zero. Por isso os arquivos são lidos com
`dtype=str` no pipeline. **Não abra e salve os CSV no Excel** — se precisar
inspecionar, abra e feche sem salvar.

**Instituição aparece em alguns trimestres e some em outros**
Pode ser real (autorização cancelada, incorporação) ou falha de extração. O
pipeline exige mínimo de 8 trimestres e reporta quem ficou de fora. Verifique
caso a caso: instituições que deixaram de operar são justamente as de maior
interesse forense, e sua exclusão introduz viés de sobrevivência que precisa
constar nas limitações.

**Cobertura de conceitos baixa mesmo com vários relatórios**
Os rótulos podem estar diferentes do que os padrões de reconhecimento esperam.
Veja a lista completa impressa pelo validador e fixe manualmente:

```python
mapa = mapeamento.resolver(rotulos, preferencias={
    "provisao_pcld": "Provisões sobre Operações de Crédito",
    "carteira_eh": "Carteira Classificada - Níveis E a H",
})
```

---

## Referências normativas

- **Resolução CMN nº 4.553/2017** — segmentação S1–S5 por Exposição/PIB
- **Resolução CMN nº 2.682/1999** — classificação de risco de crédito (AA–H) e
  constituição de provisão
- **COSIF** — Plano Contábil das Instituições do Sistema Financeiro Nacional
