# Documentação dos módulos: o que é extraído e como cada resultado é obtido

Documento técnico de referência. Percorre a cadeia inteira — do saldo COSIF
bruto até o escore de atipicidade e sua interpretação — explicando, para cada
módulo: **o que entra**, **o que sai**, **como o resultado é calculado** e
**qual decisão metodológica está embutida**.

Serve a dois propósitos: permitir que a banca audite o percurso sem ler
implementação, e permitir que você defenda cada número que aparecer no TCC.

---

## Sumário

- [0. A cadeia completa](#0)
- [1. `config` — parâmetros](#1)
- [2. `ifdata` — coleta](#2)
- [3. `segmentacao` — quem é S2 e S3](#3)
- [4. `mapeamento` — rótulos viram conceitos](#4)
- [5. `indicadores` — conceitos viram medidas de risco](#5)
- [6. `painel` — medidas viram matriz](#6)
- [7. `vazamento` — a guarda de validade](#7)
- [8. `redes` — a rede neural](#8)
- [9. `baselines` — os termos de comparação](#9)
- [10. `avaliacao` — o que as métricas medem](#10)
- [11. `interpretacao` — de escore a hipótese auditável](#11)
- [12. `benford` — triangulação independente](#12)
- [13. `diagnostico` — o registro de pendências](#13)
- [14. Rastreabilidade de um número](#14)

---

<a id="0"></a>
## 0. A cadeia completa

```
IF.data (saldos COSIF, formato longo)
    │
    ├─ ifdata.py ............... coleta, com descoberta de esquema
    ↓
Painel largo (instituição × trimestre × conta)
    │
    ├─ segmentacao.py .......... filtra S2 e S3
    ├─ mapeamento.py ........... rótulos do IF.data → 26 conceitos contábeis
    ↓
Conceitos contábeis padronizados
    │
    ├─ indicadores.py .......... 17 indicadores de risco adaptados a banco
    ↓
Indicadores
    │
    ├─ painel.py ............... winsoriza, padroniza, particiona no tempo
    ↓
Matriz numérica X  (n observações × p atributos)
    │
    ├─ redes.py ................ autoencoder: reconstrói X a partir de X
    ├─ baselines.py ............ PCA, Mahalanobis, Isolation Forest, GBM
    ↓
Escore de atipicidade (erro de reconstrução)
    │
    ├─ interpretacao.py ........ decompõe o erro por variável
    ├─ avaliacao.py ............ Precision@k, estabilidade, eventos públicos
    ├─ benford.py .............. triangulação sobre os dígitos dos saldos
    ↓
Ranking + explicação + validação
    │
    └─ diagnostico.py .......... pendências acumuladas em todo o percurso
```

Regra que atravessa a cadeia: **nenhuma etapa preenche lacuna com valor
plausível.** Ausência vira registro em `diagnostico`, nunca zero silencioso.

---

<a id="1"></a>
## 1. `config` — parâmetros

**Papel.** Concentrar toda decisão metodológica fora do código de execução,
para que possa ser auditada sem leitura de implementação.

**Principais parâmetros e o que cada um decide:**

| Parâmetro | Valor | O que decide |
|---|---|---|
| `ANOS` | 2019–2024 | Recorte temporal (24 trimestres) |
| `SEGMENTOS_ALVO` | S2, S3 | Escopo amostral |
| `FAIXAS_SEGMENTO` | S2: 1%–10%; S3: 0,1%–1% | Limiares Exposição/PIB (Res. 4.553/2017) |
| `winsor_inferior/superior` | 1% / 99% | Onde as caudas são cortadas |
| `max_ausentes_indicador` | 40% | Quando um indicador é descartado |
| `min_trimestres_instituicao` | 8 | Histórico mínimo para entrar no painel |
| `normalizacao` | rank-gauss | Como os valores são padronizados |
| `janela_temporal` | 4 | Trimestres de contexto do modelo sequencial |
| `dims_encoder` / `dim_latente` | (64, 32) / 8 | Capacidade da rede |
| `sementes` | 5 | Repetições para medir estabilidade |
| `corte_treino` | 202212 | Onde termina o treino |
| `corte_validacao` | 202312 | Onde termina a validação |
| `percentil_alerta` | 95% | A partir de onde a observação é sinalizada |
| `janela_antecedencia` | 4 | Trimestres antes do evento que contam como acerto |

**Decisão embutida.** Mudar qualquer valor aqui muda o resultado. Por isso
estão isolados: alterar um parâmetro é uma escolha declarada, não um efeito
colateral de mexer no código.

---

<a id="2"></a>
## 2. `ifdata` — coleta

**Entrada.** Nada (busca na rede) ou arquivos CSV locais.
**Saída.** DataFrame em formato longo: instituição × conta × período.

### Como o resultado é obtido

O módulo **não presume o contrato da API**. A sequência é:

1. Baixa o documento `$metadata` do serviço OData
2. Interpreta o XML (CSDL) e extrai `EntitySet`, `FunctionImport`, parâmetros
   e campos de cada tipo
3. Só então monta as requisições, casando os parâmetros pedidos com os que o
   recurso realmente declara
4. Grava cada resposta em `dados/brutos/` com carimbo de data

**Por que assim.** Nomes de recurso e coluna mudam entre versões da API. Uma
coluna presumida que não existe vira `NaN`; `NaN` imputado vira "valor típico";
e o resultado final fica errado sem nenhum erro aparecer. A descoberta em tempo
de execução transforma esse erro silencioso em mensagem explícita.

**Tratamento de falha.** Erros 4xx não são repetidos (o recurso não existe como
escrito — repetir não ajuda). Erros de rede e 5xx são repetidos quatro vezes,
com espera de 2s, 4s, 8s e 16s. Falhas isoladas não interrompem a varredura:
são registradas e o período fica ausente.

**Rastreabilidade.** Cada resposta carrega `coletado_em` em UTC. O IF.data
republica períodos quando há reapresentação de documento — a data de coleta
precisa constar no TCC.

---

<a id="3"></a>
## 3. `segmentacao` — quem é S2 e S3

**Entrada.** Painel largo com `ativo_total`.
**Saída.** Mesmo painel, filtrado, com coluna `segmento`.

### Duas rotas, em ordem de precedência

**Rota 1 — lista oficial.** Arquivo `dados/externos/segmentacao_oficial.csv`
com `cod_inst, anomes, segmento`. É a única que reproduz a classificação do
supervisor.

**Rota 2 — regra da norma.**

```
razão = ativo_total / PIB

S1: razão ≥ 10%
S2: 1%  ≤ razão < 10%
S3: 0,1% ≤ razão < 1%
S4: razão < 0,1%
```

### Por que a rota 2 emite pendência bloqueante

Três divergências em relação à norma:

1. A Res. 4.553/2017 considera **exposição**, que inclui posições fora do
   balanço; o ativo contábil é aproximação **por baixo**
2. O enquadramento é revisto em **datas-base definidas pelo BCB**, não no
   trimestre em que a razão cruza o limiar
3. Instituições próximas dos limiares oscilam de segmento entre trimestres

### Estabilização

Instituições que mudam de segmento no período recebem o **segmento modal** —
o mais frequente ao longo do recorte.

**Decisão do pesquisador, não da norma.** Está registrada como tal, com três
alternativas explícitas: segmento variável no tempo, segmento modal fixo
(adotado), ou exclusão das instituições de fronteira.

### Alerta de tamanho

Se um segmento tiver menos de 5 instituições distintas, o módulo registra
pendência: com essa amostra, qualquer diferença observada entre S2 e S3 é
compatível com ruído.

---

<a id="4"></a>
## 4. `mapeamento` — rótulos viram conceitos

**Entrada.** Lista de rótulos de coluna do IF.data.
**Saída.** Dicionário conceito → rótulo real, mais o que ficou ambíguo ou
ausente.

### Como o casamento é feito

Cada um dos 26 conceitos declara **padrões de reconhecimento** (expressões
regulares) sobre o rótulo normalizado — minúsculas, sem acento, sem pontuação,
sem espaço.

```
"Operações de Crédito"  →  "operacoesdecredito"
padrão: r"operac(oes)?decredito"  →  casa
```

**Por que não nome exato.** `df["Operações de Crédito"]` quebra se o rótulo
vier como `Operacoes de Credito`, `OPERAÇÕES DE CRÉDITO` ou
`Operações de Crédito (R$ mil)`. O reconhecimento por padrão é robusto a essas
variações; o nome exato não.

### Resolução de ambiguidade

Quando mais de um rótulo casa, escolhe-se **o mais curto** — a conta sintética
tende a ter rótulo mais enxuto que a analítica:

```
"Ativo Total"            (11 caracteres)  ← escolhido
"Ativo Total Médio"      (17)
"Ativo Total Ajustado"   (20)
```

A escolha é **sempre reportada**. Se estiver errada, fixe manualmente:

```python
mapeamento.resolver(rotulos, preferencias={"ativo_total": "Ativo Total"})
```

### Consequências declaradas

| Situação | Severidade | Efeito |
|---|---|---|
| Conceito obrigatório ausente | **BLOQUEIA** | Pipeline não roda |
| Conceito opcional ausente | COMPROMETE | Indicadores derivados são omitidos |
| Rótulo ambíguo | COMPROMETE | Escolha automática pode estar errada |

**Saída para o TCC.** `mapa.tabela()` produz o quadro de operacionalização das
variáveis. Anexe-o: é o que permite a um terceiro reproduzir a construção dos
indicadores a partir da mesma fonte.

---

<a id="5"></a>
## 5. `indicadores` — conceitos viram medidas de risco

**Entrada.** Painel com conceitos contábeis padronizados.
**Saída.** 17 indicadores, um por coluna.

Este é o módulo onde o trabalho se separa da replicação do artigo de
referência.

### O problema

Beneish (1999), Dechow et al. (2011) e Piotroski (2000) foram calibrados em
empresas **não financeiras**. Em banco:

| Componente original | Situação |
|---|---|
| `CH_INV` (estoques) | Não existe |
| Margem bruta (`GMI`) | Não há custo das mercadorias vendidas |
| Vendas (`SGI`, `DSRI`) | "Receita" não é operacional no mesmo sentido |
| Depreciação (`DEPI`) | Irrelevante frente ao tamanho do balanço |

### O critério: analogia funcional

Preserva-se a *intenção econômica* do indicador e troca-se a conta pelo
equivalente bancário.

### Classes de evidência

Cada indicador declara sua origem, e a distinção precisa aparecer no TCC:

| Classe | Significado | Quantidade |
|---|---|---|
| `LIT` | Correspondência direta na literatura citada | 1 |
| `ADAP` | Componente da literatura com substituição de conta | 10 |
| `PROP` | Proposto pelo autor a partir do arcabouço prudencial | 6 |

Os `PROP` **não têm validação empírica prévia**. São contribuição exploratória.

### Os 17 indicadores

#### Derivados de Dechow et al. (2011)

| Indicador | Fórmula | Leitura de risco |
|---|---|---|
| `soft_assets` | (Ativo − Disponibilidades − Imobilizado) / Ativo | Maior = mais discricionariedade contábil |
| `delta_carteira` | Δ₄(Carteira) / Ativo médio | Crescimento sem provisão correspondente |
| `delta_tvm` | Δ₄(TVM) / Ativo médio | Reclassificação entre categorias de TVM |
| `delta_roa` | ROA(t) − ROA(t−4) | Queda aumenta pressão por manipulação |
| `accrual_bancario` | (Lucro − proxy de caixa) / Ativo médio | Resultado por competência, não por caixa |
| `delta_capital` | 1 se Δ₄(Capital social) > 0 | Emissão coincide com incentivo a reportar bem |

`Δ₄` = variação em relação ao **mesmo trimestre do ano anterior**. Interanual,
não trimestral: o balanço bancário tem sazonalidade (dezembro concentra baixas
e constituições), e a diferença trimestral confundiria sazonalidade com
anomalia.

**Sobre o `accrual_bancario`.** O IF.data não traz demonstração de fluxo de
caixa. O proxy soma de volta a despesa de provisão (item sem efeito caixa no
período) e desconta a variação de outros créditos. **É aproximação declarada** —
deve constar nas limitações.

#### Derivados de Beneish (1999)

| Indicador | Fórmula | Leitura de risco |
|---|---|---|
| `gmi_bancario` | NIM(t−4) / NIM(t) | > 1 indica deterioração de margem |
| `sgi_bancario` | Carteira(t) / Carteira(t−4) | Crescimento acelerado |
| `aqi_bancario` | (Outros créditos + Intangível + Créditos tributários) / Ativo | Migração para ativos de mensuração frouxa |
| `levi_bancario` | Ativo / Patrimônio líquido | Alavancagem crescente |
| `sgai_bancario` | \|Despesa administrativa\| / \|Resultado intermediação\| | Deterioração de eficiência |

`NIM` = Resultado de intermediação / Ativo médio.

#### Propostos a partir do arcabouço prudencial

| Indicador | Fórmula | Leitura de risco |
|---|---|---|
| `cobertura_provisao` | \|Provisão\| / Carteira E–H | **Queda com carteira E–H estável é o padrão de subprovisionamento** |
| `intensidade_provisao` | \|Provisão\| / Carteira total | Redução abrupta sem melhora de inadimplência |
| `descasamento_provisao_inad` | Δ₄(Inadimplência) − Δ₄(Intensidade de provisão) | Inadimplência sobe, provisão não acompanha |
| `peso_credito_tributario` | Créditos tributários / PL | Capital sustentado por lucro futuro |
| `folga_basileia` | Índice de Basileia − piso | Folga pequena cria incentivo a gerenciar RWA ou resultado |
| `dependencia_nao_recorrente` | \|Outras receitas op.\| / \|Lucro líquido\| | Resultado concentrado em linha residual |

**Por que esses seis importam.** Subprovisionar é o mecanismo mais direto de
inflar resultado em instituição financeira, e **nenhum componente de Beneish,
Dechow ou Piotroski o captura**. Se o ranking de atributos que explicam a
atipicidade (seção 11) for dominado por indicadores `PROP`, o trabalho tem
argumento empírico de que a adaptação ao contexto bancário foi o que produziu
informação.

**Ressalva no `folga_basileia`.** O piso está fixo em 10,5%. O mínimo aplicável
varia por instituição e por data (adicionais de capital principal). Registrado
como ponto de correção.

### Divisão protegida

Denominador nulo **ou negativo** produz ausente, não número. PL negativo
inverteria o sinal do indicador e produziria leitura invertida — prefere-se
ausente a errado.

---

<a id="6"></a>
## 6. `painel` — medidas viram matriz

**Entrada.** Indicadores.
**Saída.** Matriz numérica particionada em treino, validação e teste.

### Sequência e justificativa

**1. Filtro de histórico** — exige ≥ 8 trimestres por instituição.
*Efeito colateral declarado:* introduz **viés de sobrevivência**. Instituições
que deixaram de operar no período — justamente as de maior interesse forense —
são as mais propensas a ter histórico curto. Registrado como pendência.

**2. Descarte de esparsos** — remove indicador com > 40% de ausência.
Se o descarte atingir os indicadores `PROP`, o estudo volta a ser aplicação de
modelo de empresa não financeira. Reportado.

**3. Winsorização por trimestre** — corta em 1% e 99%, dentro de cada
trimestre.
*Por que por trimestre e não global:* contas COSIF mudam de escala ao longo de
2019–2024; cortar contra a distribuição do próprio trimestre preserva a
comparação transversal. O artigo de referência reporta curtose acima de 29.000
no DF-Score — sem winsorizar, qualquer modelo baseado em distância ou gradiente
é dominado por poucos pontos.

**4. Z-score por pares** — padroniza dentro de (segmento, trimestre):

```
z = (valor − mediana do grupo) / (MAD do grupo × 1,4826)
```

*Por que mediana e MAD:* com dezenas de instituições e caudas pesadas, a média
é puxada pelo próprio caso extremo que se quer detectar. O fator 1,4826 torna
o MAD comparável ao desvio-padrão sob normalidade.

*Por que por pares:* a pergunta é "esta instituição destoa dos seus pares
**agora**?". Sem esse passo, o modelo aprende principalmente **tamanho** e
**ciclo econômico**.

**5. Normalização rank-gauss** — converte para posto na distribuição de treino
e depois para quantil da normal padrão. Robusta a outliers residuais.

*Ajustada apenas no treino.* Ajustar no conjunto todo é vazamento — o modelo
teria visto a distribuição do futuro.

**6. Marcação de ausentes** — cada atributo ganha `faltante_<x>` (0 ou 1), e o
valor faltante vira 0 **depois** da normalização, que é a posição central.

*Por que não imputar a média:* a média imputada entra como "valor típico" e
reduz artificialmente o erro de reconstrução justamente onde há menos
informação — o modelo ficaria mais confiante onde sabe menos.

### Partição temporal

```
treino     ≤ 202212     (2019–2022)
validação  202303–202312 (2023)
teste      ≥ 202403     (2024)
```

**Nunca aleatória.** Ver seção 7.

---

<a id="7"></a>
## 7. `vazamento` — a guarda de validade

**Papel.** Impedir que o pipeline produza métrica inflada sem que ninguém
perceba. É a contribuição metodológica central do trabalho.

### 7.1 Circularidade entre atributos e rótulo

**O que foi observado no artigo de referência.**

O DF-Score é definido (Tabela 3) como a soma de oito componentes:

```
DF-Score = RSST_ACC + CH_REC + CH_INV + SOFT_ASSETS
         + CH_CS + CH_CM + CH_ROA + CH_FCF
```

O vetor de atributos usado para prever o DF-Score (seção 3.2.2) é composto
**desses mesmos oito componentes**. As métricas reportadas (Tabela 5: acurácia
0,995; AUC-ROC 0,999) são compatíveis com um modelo que reaprende uma
identidade aritmética que lhe foi dada de entrada.

**Isso não invalida o artigo** — cujo objeto é a relação entre risco de fraude e
opinião de auditoria, estimada depois por IV-2SLS, com o XGBoost servindo de
etapa intermediária. Invalida a leitura de que "AUC 0,999 demonstra capacidade
de detecção".

**O que a guarda faz.**

1. Identifica atributos que são componentes algébricos do rótulo, inclusive
   através de derivações (`z_par_x` e `faltante_x` continuam sendo `x`)
2. Filtra ou interrompe o treino **antes** de a métrica ser produzida
3. Audita empiricamente correlações de posto ≥ 0,98 com o rótulo, que denunciam
   vazamento não declarado

**O resultado que isso produz.** O notebook (seção 15) roda as duas versões e
reporta lado a lado. Em ensaio sobre painel sintético:

| Modelo | AUC-ROC |
|---|---|
| XGBoost com os componentes do rótulo | 0,967 |
| LightGBM com os componentes do rótulo | 0,972 |
| XGBoost sem os componentes | 0,603 |
| LightGBM sem os componentes | 0,610 |

A diferença **é um resultado do TCC**: quantifica quanto da performance
reportada em desenhos desse tipo vem de circularidade e não de capacidade
preditiva.

> Os números acima vêm de painel sintético de verificação. A magnitude com
> dados reais será outra; o mecanismo é o mesmo.

### 7.2 Vazamento temporal

Divisão aleatória 70/30 sobre **painel** coloca trimestres futuros da mesma
instituição no treino e passados no teste. Como indicadores contábeis são
altamente persistentes dentro da instituição, o modelo passa a "reconhecer a
instituição" em vez de generalizar.

`auditar_particao_temporal()` verifica e **bloqueia** se houver sobreposição.

`comparar_desenhos()` produz tabela confrontando partição cronológica e
aleatória — evidência direta, e barata, de um problema recorrente na literatura
aplicada.

---

<a id="8"></a>
## 8. `redes` — a rede neural

**Entrada.** Matriz X (n × p).
**Saída.** Escore por observação, erro por atributo, métricas de estabilidade.

### 8.1 Por que autoencoder e não classificador

| | Classificador | Autoencoder |
|---|---|---|
| Aprende | `f(x) → y` | `f(x) → x` |
| Precisa de rótulo | **Sim** | Não |
| Perda | entropia cruzada | erro quadrático de reconstrução |
| Representa | fronteira entre classes | variedade dos dados normais |
| Escore de anomalia | probabilidade prevista | erro de reconstrução |

**Não existe rótulo público de fraude bancária no Brasil.** Um classificador
exigiria inventar o alvo, e a métrica passaria a medir concordância com a
invenção — que é precisamente o problema da seção 7.1.

### 8.2 O mecanismo, verificado empiricamente

O poder de discriminação vem principalmente de **a rede só ver dados normais no
treino**. Ela se torna boa em reconstruir a região do espaço onde os dados de
treino vivem, e se comporta de forma arbitrária fora dela. O gargalo ajuda, mas
não é o mecanismo principal.

Verificação com dados sintéticos (20 variáveis governadas por 3 fatores):

| n treino | Erro normal (treino) | Erro normal (novo) | Erro atípico | Razão real |
|---|---|---|---|---|
| 40 | 0,00026 | 0,05075 | 2,7433 | 52,8× |
| 100 | 0,00265 | 0,01694 | 2,6305 | 140,2× |
| 800 | 0,00557 | 0,00665 | 2,3192 | 315,8× |
| 3000 | 0,00596 | 0,00610 | 2,4374 | 338,5× |

**Leitura.** Com n = 40, o erro no treino é 195 vezes menor que em observações
normais nunca vistas: a rede **memorizou**. A discriminação medida no treino
pareceria excelente e seria artefato — uma instituição normal inédita seria
sinalizada como atípica.

Isso justifica diretamente três decisões do pipeline: corte temporal,
monitoramento da razão parâmetros/observações, e repetição por sementes.

### 8.3 As três arquiteturas

**`AutoencoderTabular`** — denoising, com gargalo estreito.
Entrada recebe ruído gaussiano (σ = 0,10); o alvo é o vetor limpo. Isso força
aprender estrutura robusta em vez da identidade.

```
p → 64 → 32 → 8 → 32 → 64 → p
```

Escore = erro quadrático médio de reconstrução.

**`AutoencoderSequencial`** — GRU que lê 4 trimestres e prevê o seguinte.
Escore = erro de previsão. Mede **quebra estrutural** na trajetória da
instituição, que é mais próximo da intuição de auditoria ("mudou de
comportamento") do que a atipicidade transversal.

Os dois escores são complementares: uma instituição pode ser sempre diferente
dos pares sem nunca mudar (alto no autoencoder, baixo no GRU), ou mudar
bruscamente permanecendo dentro do intervalo dos pares (o inverso).

**`RedeHibrida`** — codificador compartilhado, com cabeça de reconstrução e
cabeça de classificação. Só deve ser usada com a guarda de circularidade ativa.

### 8.4 Controles de qualidade

**Ensemble por sementes.** Cinco inicializações; escore final é a **mediana**.
A correlação de posto entre sementes mede confiabilidade: abaixo de 0,80, o
ranking depende mais da inicialização que dos dados, e nenhuma instituição
individual pode ser apontada.

**Parada antecipada.** Paciência de 40 épocas sobre a perda de validação;
restaura os melhores pesos.

**Alerta de sobreparametrização.** Se o número de parâmetros exceder o de
observações, emite pendência. Com S2+S3 (~800 observações) isso é esperado — e
é a limitação estrutural de aplicar rede neural a um painel desse porte.

---

<a id="9"></a>
## 9. `baselines` — os termos de comparação

**Papel.** Responder à pergunta que a banca fará: a rede acrescenta algo sobre
métodos mais simples e mais auditáveis?

| Método | O que é | Escore |
|---|---|---|
| **PCA** | Reconstrução linear | Erro de reconstrução |
| **Mahalanobis robusto** | Distância estatística com covariância de determinante mínimo | Distância |
| **Isolation Forest** | Árvores, sem suposição de distribuição | Grau de isolamento |
| **XGBoost / LightGBM** | Gradient boosting (previstos no projeto de pesquisa) | Probabilidade |

**Por que Mahalanobis robusto e não clássico.** A covariância amostral comum é
estimada **com os próprios pontos atípicos dentro**, o que mascara a anomalia.
O estimador de determinante mínimo ignora a fração mais discrepante ao estimar.

**Comparação em posto percentual.** Escores brutos de métodos diferentes não
são comparáveis — as escalas são incomensuráveis. O posto dentro do próprio
método é a única comparação legítima, e é também como o escore seria usado na
prática (priorização de carga de auditoria).

**Como ler a concordância.** Correlação alta com o PCA significa que a rede
redescobre o que um método linear já dizia — e o custo de interpretabilidade
não se justifica. Correlação baixa exige explicar caso a caso o que a rede
enxerga a mais. **As duas leituras são resultados publicáveis; não fazer a
comparação não é.**

---

<a id="10"></a>
## 10. `avaliacao` — o que as métricas medem

**O problema central.** Sem rótulo de fraude não há acurácia, AUC-ROC nem F1 —
essas métricas exigem contra o que comparar.

Três formas legítimas, em ordem decrescente de força probatória:

### 10.1 Validação por eventos públicos

Eventos datados e verificáveis em fonte primária: liquidação extrajudicial,
regime de administração especial temporária, intervenção, cancelamento de
autorização, processos administrativos sancionadores.

**Como o positivo é definido.** Uma observação (instituição, trimestre) é
positiva quando cai na janela de 4 trimestres **anteriores** ao evento.

**Trimestres posteriores ao evento são excluídos.** Depois da intervenção o
balanço reflete a intervenção; acertar ali não é previsão, é tautologia.

**Métricas produzidas:**

| Métrica | Definição | Por que importa |
|---|---|---|
| `precisao_em_k` | acertos entre os k primeiros / k | O auditor examina as k primeiras posições |
| `recall_em_k` | acertos entre os k primeiros / total de positivos | Cobertura |
| `ganho_sobre_acaso` | precisão@k / taxa base | Quanto o modelo supera seleção aleatória |
| `trimestres_de_antecedencia` | distância entre o primeiro alerta e o evento | Valor prático para auditoria |

**Por que não AUC-ROC como métrica principal.** AUC integra sobre toda a curva,
inclusive faixas que nenhum auditor examinaria. Em detecção de evento raro com
recurso finito, a métrica pertinente é precisão no topo da lista.

**Alerta automático.** Com menos de 10 positivos, o módulo registra pendência:
o intervalo de confiança fica largo demais para sustentar comparação entre
modelos, e o honesto é apresentar como estudo de caso.

### 10.2 Coerência interna

**Estabilidade entre sementes** — correlação de posto entre inicializações.

**Persistência trimestral** — correlação de posto do escore entre trimestres
consecutivos. Fraude contábil é fenômeno persistente; um escore que muda de
ordenação a cada trimestre está medindo ruído, não condição da instituição.
Abaixo de 0,30, o módulo emite pendência.

**Concordância entre métodos** — ver seção 9.

### 10.3 Rótulo fraco

Construído a partir dos próprios indicadores: composto de z-scores absolutos
acima do percentil 90.

**Não é fraude.** É "combinação atípica de sinais contábeis de risco". Serve
apenas para comparar arquiteturas entre si, sob guarda de circularidade.

O módulo **exige** que a métrica seja nomeada no TCC como *"concordância com o
rótulo fraco"*, jamais como *"detecção de fraude"* — e registra pendência
lembrando disso.

---

<a id="11"></a>
## 11. `interpretacao` — de escore a hipótese auditável

**Papel.** Um escore sem explicação é inútil para auditoria. Ninguém abre
procedimento com "o modelo deu 0,93".

### 11.1 Decomposição do erro

Para autoencoder, a decomposição é **exata**, não estimada:

```
erro_total(i) = Σⱼ (x̂ᵢⱼ − xᵢⱼ)²
participação do atributo j = (x̂ᵢⱼ − xᵢⱼ)² / erro_total(i)
```

**Vantagem sobre SHAP.** SHAP estima a contribuição de cada variável por
amostragem de coalizões. Aqui a contribuição é aritmética: o erro total é a
soma dos erros por variável. Para auditoria, onde o achado precisa virar
procedimento, essa diferença pesa.

### 11.2 Saídas

| Função | O que produz |
|---|---|
| `decompor_erro` | Uma linha por (instituição, trimestre, atributo) entre os 5 maiores contribuintes |
| `perfil_por_instituicao` | Trajetória dos motivos ao longo do tempo |
| `ranking_atributos` | Quais indicadores explicam a atipicidade no agregado |
| `narrativa` | Frase auditável, em português |
| `gradientes_integrados` | Atribuição para a cabeça supervisionada |

### 11.3 O teste que valida a adaptação

`ranking_atributos()` cruzado com a classe de evidência dos indicadores
responde: **a atipicidade detectada vem dos indicadores prudenciais propostos
(`PROP`) ou da transposição dos modelos originais (`ADAP`)?**

Se vier dos `PROP`, o trabalho tem argumento empírico de que a adaptação ao
contexto bancário foi o que produziu informação. É o achado metodológico mais
forte que este desenho pode entregar.

### 11.4 Linguagem da narrativa

Deliberadamente redigida em termos de **atipicidade**, nunca de fraude:

> "Instituição X, 202403: o comportamento observado difere do padrão dos pares
> principalmente em cobertura_provisao (41% do erro) — Queda da cobertura com
> carteira E-H estável é o padrão esperado de subprovisionamento. Trata-se de
> hipótese de trabalho para direcionamento de procedimento de auditoria, não de
> indício de irregularidade."

---

<a id="12"></a>
## 12. `benford` — triangulação independente

**Por que existe.** Rede, PCA e Mahalanobis derivam do **mesmo** conjunto de
indicadores. Se os três apontarem a mesma instituição, isso não é corroboração
— é a mesma medida contada três vezes.

Benford opera sobre outra coisa: a distribuição dos **dígitos** dos saldos
publicados, independentemente de qualquer razão contábil construída aqui.

### Como funciona

Frequência esperada do primeiro dígito significativo:

```
P(d) = log₁₀(1 + 1/d),  d ∈ {1,...,9}
```

Estatística de conformidade — desvio absoluto médio:

```
MAD = (1/9) Σ |observado(d) − esperado(d)|
```

Limiares de Nigrini (2012), primeiro dígito:

| MAD | Classificação |
|---|---|
| 0,000 – 0,006 | conformidade próxima |
| 0,006 – 0,012 | conformidade aceitável |
| 0,012 – 0,015 | conformidade marginal |
| > 0,015 | não conforme |

### Três ressalvas obrigatórias no TCC

1. Saldos do IF.data já são **agregados**; a conformidade é mais fraca em
   agregados do que em lançamentos individuais
2. Contas com piso, teto ou valor regulado violam a premissa de escala livre
3. **Desvio de Benford não é indício de fraude** — arredondamento, conversão de
   moeda e reclassificação produzem o mesmo sintoma

Instituições com menos de 300 saldos não são classificadas: o MAD é instável e
os limiares não se sustentam.

---

<a id="13"></a>
## 13. `diagnostico` — o registro de pendências

**Papel.** Qualquer módulo registra uma limitação **no momento em que ela
aparece**, com área responsável e ação pedida. Ao final, a seção 16 do notebook
consolida tudo.

### Três severidades

| Nível | Significado |
|---|---|
| `BLOQUEIA RESULTADO` | Os escores não devem ser reportados no TCC |
| `COMPROMETE INTERPRETAÇÃO` | Pode ser reportado, com ressalva explícita |
| `OBSERVAÇÃO` | Transparência; não invalida nada |

### A decisão de projeto por trás

Um indicador que não pôde ser construído **não vira zero nem `NaN`
silencioso** — vira texto no relatório final. Ausência escondida é o modo mais
comum de um pipeline produzir números que ninguém consegue defender depois.

**Aviso registrado no próprio relatório:** ausência de pendências não equivale
a validação metodológica. Significa apenas que nenhuma verificação
automatizada falhou.

---

<a id="14"></a>
## 14. Rastreabilidade de um número

Exemplo completo: o escore da instituição X no trimestre 202403.

```
1. IF.data, relatório de balanço, 202403
   "Provisão sobre Operações de Crédito" = 15.000 (mil reais)
   "Carteira Classificada - Níveis E a H" = 20.000
       ↓  mapeamento.resolver()
2. provisao_pcld = 15000 ; carteira_eh = 20000
       ↓  indicadores.construir()
3. cobertura_provisao = |15000| / 20000 = 0,75
       ↓  painel.winsorizar()  — dentro do trimestre 202403
4. valor mantido (dentro de [p1, p99])
       ↓  painel.z_por_pares()  — dentro de (S3, 202403)
5. mediana do grupo = 1,10 ; MAD = 0,15
   z = (0,75 − 1,10) / (0,15 × 1,4826) = −1,57
       ↓  painel.Escalador.transformar()  — rank-gauss ajustado no treino
6. valor normalizado
       ↓  redes.treinar_autoencoder()
7. reconstruído: −0,30  |  observado: −1,57
   erro do atributo = (−0,30 − (−1,57))² = 1,61
       ↓  soma sobre os atributos
8. escore = média dos erros = 0,42  → posto percentual 0,97
       ↓  interpretacao.decompor_erro()
9. cobertura_provisao responde por 41% do erro total
       ↓  interpretacao.narrativa()
10. "difere do padrão dos pares principalmente em cobertura_provisao
     (41% do erro) — queda da cobertura com carteira E-H estável é o
     padrão esperado de subprovisionamento"
```

**Cada passo é reversível e auditável.** É isso que permite defender o número
na banca: não há caixa-preta entre o saldo publicado e a afirmação final.

> Os valores acima são ilustrativos, para mostrar o encadeamento. Substitua
> pelos números da sua execução ao usar no TCC.

---

## Referências

BENEISH, M. D. The detection of earnings manipulation. *Financial Analysts
Journal*, v. 55, n. 5, p. 24-36, 1999.

BENYASRISAWAT, P.; OUNLERT, N. Fraud risk and audit opinions across countries.
*Journal of Risk and Financial Management*, v. 19, n. 1, p. 26, 2026.

BRASIL. Banco Central do Brasil. **Resolução CMN nº 2.682/1999**; **Resolução
CMN nº 4.553/2017**.

DECHOW, P. M. et al. Predicting material accounting misstatements.
*Contemporary Accounting Research*, v. 28, n. 1, p. 17-82, 2011.

DYCK, A.; MORSE, A.; ZINGALES, L. How pervasive is corporate fraud? *Review of
Accounting Studies*, v. 28, 2020.

NIGRINI, M. J. *Benford's law: applications for forensic accounting, auditing,
and fraud detection*. Hoboken: Wiley, 2012.

PIOTROSKI, J. D. Value investing. *Journal of Accounting Research*, v. 38,
p. 1-41, 2000.
