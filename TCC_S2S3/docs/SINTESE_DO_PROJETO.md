# Síntese do projeto

Documento de fechamento: o que foi construído, o que foi descoberto sobre os
dados, os problemas enfrentados e as extensões discutidas mas não executadas.

Projeto de apoio ao TCC *Auditorias em instituições financeiras dos segmentos
S2 e S3* — Fernando Ulerich Fonseca, Ciências Contábeis, UFF.

---

## 1. O objeto

Pipeline de rede neural sobre dados públicos do **IF.data/COSIF** (Banco
Central do Brasil), período 2019-03 a 2024-12, para identificar **atipicidade
contábil** em instituições financeiras dos segmentos S2 e S3.

A premissa que atravessa todo o trabalho: **o código não detecta fraude**. Mede
distância entre o comportamento de uma instituição e o padrão dos seus pares e
do seu próprio histórico. Fraude é qualificação jurídica — exige intenção
comprovada, contraditório e decisão de autoridade competente.

Isso não é cautela retórica. Dyck, Morse e Zingales (2020) estimam que apenas
cerca de um terço das fraudes corporativas é detectado; logo, o conjunto de
instituições sem evento público conhecido mistura instituições íntegras e
irregularidades que nunca vieram a público. Nenhum modelo treinado nesses dados
separa as duas coisas, e nenhum resultado deve ser redigido como se separasse.

---

## 2. As três decisões metodológicas centrais

### 2.1 Autoencoder em vez de classificador

Não existe rótulo público de fraude bancária no Brasil. Um classificador
exigiria inventar o alvo, e a métrica passaria a medir concordância com a
invenção.

O autoencoder dispensa rótulo: aprende a região do espaço onde vivem os dados
normais e pontua pelo erro de reconstrução.

**Verificação empírica feita** (dados sintéticos, para entender o mecanismo): o
poder de discriminação vem principalmente de a rede **só ver dados normais no
treino**, não do gargalo. Com amostra pequena (n=40) ela memoriza — erro de
0,00026 no treino contra 0,05075 em normais inéditos — e o ganho aparente
desaparece quando medido fora da amostra.

| n treino | Erro (treino) | Erro (normais novos) | Erro (atípicos) | Razão real |
|---|---|---|---|---|
| 40 | 0,00026 | 0,05075 | 2,7433 | 52,8× |
| 100 | 0,00265 | 0,01694 | 2,6305 | 140,2× |
| 800 | 0,00557 | 0,00665 | 2,3192 | 315,8× |
| 3000 | 0,00596 | 0,00610 | 2,4374 | 338,5× |

Isso justifica diretamente o corte temporal, o monitoramento da razão
parâmetros/observações e a repetição por sementes.

### 2.2 Guarda de circularidade

**A contribuição metodológica mais forte do trabalho.**

No artigo de referência (Benyasrisawat e Ounlert, 2026), o XGBoost prevê o
DF-Score usando como atributos os **próprios componentes que definem o
DF-Score** — que é, por construção, a soma deles. As métricas reportadas
(acurácia 0,995; AUC-ROC 0,999) são compatíveis com um modelo que reaprende
uma identidade aritmética, não com um modelo que detecta fraude.

Isso não invalida o artigo: o objeto dele é a relação entre risco de fraude e
opinião de auditoria, estimada depois por IV-2SLS. Invalida a leitura de que
"AUC 0,999 demonstra capacidade de detecção".

O módulo `vazamento.py` detecta e bloqueia esse padrão, inclusive através de
derivações. O notebook executa as duas versões e reporta lado a lado. Em ensaio
sobre painel sintético:

| Modelo | AUC-ROC |
|---|---|
| XGBoost com os componentes do rótulo | 0,967 |
| LightGBM com os componentes do rótulo | 0,972 |
| XGBoost sem os componentes | 0,603 |
| LightGBM sem os componentes | 0,610 |

A diferença é resultado do TCC: quantifica quanto da performance reportada em
desenhos desse tipo vem de circularidade.

### 2.3 Indicadores adaptados ao balanço bancário

Beneish, Dechow e Piotroski foram calibrados em empresas não financeiras. Em
banco não há estoque, custo das mercadorias vendidas nem vendas no mesmo
sentido. A reconstrução é por **analogia funcional**: preserva a intenção
econômica e troca a conta pelo equivalente bancário.

Dos 21 indicadores construídos: **1 LIT** (correspondência direta), **9 ADAP**
(adaptação de conta) e **11 PROP** (proposições a partir do arcabouço
prudencial, sem validação empírica prévia).

---

## 3. O que descobrimos sobre os dados

Cada item abaixo foi encontrado confrontando o código com arquivos reais, e
cada um teria contaminado o resultado em silêncio.

### 3.1 Cabeçalho hierárquico — a descoberta mais importante

As exportações usam **de uma a três linhas de cabeçalho**: a primeira traz os
grupos sintéticos, as seguintes as contas analíticas.

| Relatório | Linhas de cabeçalho |
|---|---|
| Resumo, Segmentação | 1 |
| Ativo | 2 |
| DRE, Passivo, Informações de Capital | 3 |

Ler só a primeira produzia dois defeitos simultâneos: perdia as contas
analíticas e tratava as demais linhas de cabeçalho como instituições.

E era exatamente ali que estavam as contas que sustentam os indicadores
prudenciais: `Provisão sobre Operações de Crédito (d2)`, `Resultado de Provisão
para Créditos de Difícil Liquidação (b5)`, serviços, pessoal e administrativas.

**Antes dessa descoberta eu havia concluído que provisão e despesa de provisão
não existiam na base. Estava errado.**

Validação: a identidade contábil do Itaú em 2024-03 fecha exatamente —
`741.455.019 + (−48.436.033) = 693.018.986`.

### 3.2 Rodapé com totais agregados

Cada exportação anexa ao final 40 linhas com a legenda dos códigos e os
**totais por categoria** — `S2 - Segmento 2` com R$ 1,3 trilhão, por exemplo.
Mantidas, entrariam no painel como instituições gigantes.

Sintoma que denunciou: o ativo total somava R$ 45 trilhões em vez dos R$ 9,18
trilhões corretos do SFN em 2019.

### 3.3 Variantes de rótulo ao longo do tempo

As letras de referência mudam quando o BCB acrescenta parcela ao cálculo — o
RWA passa de `(i) = (f)+(g)+(h)` para `(j) = (f)+(g)+(h)+(i)` com o RWAsp.

São variantes do mesmo conceito e nunca coexistem no mesmo trimestre. Somá-las
duplicaria; a solução é coalescência. `patrimonio_liquido` tinha **74% de
ausência** e caiu para **0,27%**.

### 3.4 A coluna SR resolve a segmentação

O relatório Resumo publica o enquadramento oficial S1–S5 na coluna `SR`. Isso
eliminou uma **pendência bloqueante**: não é mais preciso reconstruir a
segmentação pela razão Exposição/PIB, que é aproximação questionável.

### 3.5 Convenção de sinais

Provisões e despesas vêm com sinal negativo, para que as identidades contábeis
fechem por soma. Os indicadores que exigem magnitude aplicam valor absoluto
explicitamente.

### 3.6 Quebra de leiaute em 2025

Teste com contrafactual (variação sob leiaute constante × variação na
transição), sobre a razão conta/ativo de ~1.345 instituições:

| \|Δ carteira/ativo\| | 2024-09→12 (constante) | 2024-12→2025-03 (alterado) | Razão |
|---|---|---|---|
| Mediana | 0,0127 | 0,0227 | **1,8×** |
| Percentil 90 | 0,0603 | 0,1117 | **1,9×** |
| Acima de 0,05 | 13,5% | 27,9% | **2,1×** |

`Passivo Exigível` é renomeação (razão 1,05×). **`Carteira de Crédito` é
redefinição.** Como a carteira alimenta quatro indicadores e a variação
interanual de 2025 compararia com 2024, atravessando a quebra, o recorte foi
mantido em 2019–2024 — agora com fundamento medido, não por conveniência.

---

## 4. Estado do código

| | |
|---|---|
| Módulos | 15 |
| Linhas de código | ~5.800 |
| Testes automatizados | 14 (todos passando) |
| Conceitos contábeis mapeados | 52 |
| Indicadores construídos | 21 |
| Documentação | ~3.000 linhas em 8 documentos |

### Arquitetura

```
ifdata.py         leitura, cabeçalho hierárquico, conversão numérica
consolidacao.py   os 6 relatórios → painel único de conceitos
segmentacao.py    S2/S3 a partir da coluna SR
mapeamento.py     rótulos → conceitos, com diagnóstico
indicadores.py    os 21 indicadores adaptados
painel.py         winsorização, z-score por pares, partição temporal
vazamento.py      guarda de circularidade
redes.py          autoencoder denoising, GRU sequencial, rede híbrida
baselines.py      PCA, Mahalanobis robusto, Isolation Forest, XGBoost, LightGBM
avaliacao.py      Precision@k, estabilidade, validação por eventos
interpretacao.py  decomposição exata do erro por variável
benford.py        triangulação independente
diagnostico.py    registro de pendências
```

### Painel produzido

| | |
|---|---|
| Painel completo | 31.819 observações, 1.629 instituições, 24 trimestres |
| **Amostra S2/S3** | **1.347 observações, 72 instituições** |
| Composição | 9 em S2 (154 obs) e 66 em S3 (1.193 obs) |
| Cobertura dos 6 conceitos obrigatórios | 99,73% |
| Pendências abertas | 3, todas legítimas |

### Piso de capital

| Grupo | Piso | Observações | Instituições |
|---|---|---|---|
| Regime pleno | 10,5 p.p. | 1.236 | 62 |
| Cooperativas (`b3S`, `b3C`) | faixa 13–18 p.p. | 111 | 10 |

Como o requerimento das cooperativas é faixa e o IF.data não publica o
enquadramento exato, o pipeline calcula os dois extremos e marca as
**42 observações em 7 instituições** onde a conclusão muda conforme a escolha.

---

## 5. Problemas enfrentados

| Problema | Natureza | Status |
|---|---|---|
| API do IF.data inacessível | Rede corporativa | Contornado: extração manual, 144 arquivos |
| Cabeçalho hierárquico não lido | **Código** | Corrigido |
| Rodapé de legenda no painel | **Código** | Corrigido |
| Variantes de rótulo | **Código** | Corrigido |
| `dados 2020-06 Resumo.csv` continha Segmentação | Dados | Corrigido pelo autor |
| Arquivos renomeados para `.pyl`/`.ipykernel` | Ambiente | Corrigido |
| Extração de zip em destino errado | Ambiente | Corrigido |
| Webview do VS Code corrompida | Ambiente | Script de reparo entregue |
| Push ao GitHub | Permissão | **Aberto** — app do Claude não instalado no repositório |

Vale a distinção: apenas três foram defeitos de código. Os demais foram
ambiente ou dados de origem — e todos os de código só apareceram porque o
pipeline foi confrontado com arquivos reais.

---

## 6. Extensões discutidas

### 6.1 Fontes oficiais complementares

Documentadas em `FONTES_COMPLEMENTARES.md`, por ordem de impacto:

**Eventos do BCB** (liquidação extrajudicial, RAET, intervenção) — sem eles a
seção 14 do notebook não roda e a conclusão fica restrita a "atipicidade". Com
eles, passa a ser possível afirmar antecedência: *"o escore subiu N trimestres
antes de eventos que efetivamente ocorreram"*.

**CVM — DFP e ITR de bancos listados.** A mais interessante metodologicamente,
por duas razões:

- traz a **demonstração dos fluxos de caixa**, que permitiria substituir o
  *proxy* do `accrual_bancario` por accrual calculado com FCO real;
- traz o **parecer do auditor independente** — que é exatamente a variável
  dependente de Benyasrisawat e Ounlert. Com ela seria possível reproduzir o
  **segundo estágio** do artigo de referência (IV-2SLS), e não apenas a
  construção do índice.

Limitação: poucos bancos S2/S3 têm capital aberto. Vira subamostra, análise
complementar.

**Cadastro de instituições (Unicad)** — permite distinguir saída por
incorporação de saída por liquidação, resolvendo o viés de sobrevivência que
hoje é apenas declarado.

Demais: sancionadores do BCB e da CVM, Receita Federal (CNPJ), SGS, IBGE,
ESTBAN, SCR.

### 6.2 2025 como conjunto de validação externa

Chegou a ser proposto e foi **descartado com base em teste**. Os indicadores de
variação interanual de 2025 dependem de 2024, atravessando a quebra de leiaute.
Um *holdout* contaminado é pior que nenhum: produziria métrica de generalização
que mede efeito de mudança contábil.

Reavaliação possível a partir de 2026-03, quando houver quatro trimestres
consecutivos sob o leiaute vigente.

### 6.3 Triangulação por Benford

Rede, PCA e Mahalanobis derivam do mesmo conjunto de indicadores — se os três
apontarem a mesma instituição, é a mesma medida contada três vezes. Benford
opera sobre os dígitos dos saldos publicados, independentemente de qualquer
razão construída. Implementado em `benford.py`, com os limiares de MAD de
Nigrini (2012).

### 6.4 Modelo sequencial (GRU)

Complementa o autoencoder: enquanto este mede atipicidade **transversal**
(diferente dos pares agora), o GRU mede **quebra estrutural** (mudou de
comportamento). Uma instituição pode ser sempre diferente sem nunca mudar, ou
mudar bruscamente dentro do intervalo dos pares.

### 6.5 Comparação obrigatória com métodos simples

PCA, Mahalanobis robusto e Isolation Forest sobre o mesmo insumo, comparados em
posto percentual. Se a rede não superar o PCA, a não linearidade não está
comprando nada — e dizer isso é resultado. XGBoost e LightGBM permanecem como
termo de comparação, sob a guarda de circularidade.

### 6.6 Pré-treino fora do escopo

Aprender a variedade de normalidade em S4/S5 (muito mais numerosas) e pontuar
apenas S2/S3, resolvendo o porte amostral. **Mantido desligado** por padrão:
altera o que se afirma sobre a fonte da normalidade aprendida, e é decisão do
orientador.

---

## 7. O que falta

### No pipeline

1. Executar da seção 7 do notebook em diante — painel, partição, autoencoder
2. Preencher `dados/externos/eventos_publicos.csv`
3. Confirmar o enquadramento das 7 cooperativas na zona de incerteza
4. Investigar as 12 observações com folga de Basileia negativa

### No texto do TCC

Detalhado no Apêndice A do `HISTORICO.md`. As três principais:

- o **título anuncia LLMs**, mas o método é gradient boosting e redes neurais,
  que não são LLMs;
- a seção 2.4 atribui ao artigo de referência a combinação de "M-Score e
  F-Score"; ele usa **DF-Score e PF-Score**;
- a descrição de Hanifah et al. (2024) não corresponde ao título da obra
  referenciada.

Faltam Cressey e Piotroski nas referências; sobram Jensen/Meckling e
Lundberg/Lee, citados na lista e ausentes no corpo.

---

## 8. O que o trabalho poderá afirmar

**Poderá:**

- que determinadas instituições-trimestre se afastam do padrão dos pares e do
  próprio histórico, com a decomposição indicando em quais contas;
- que o afastamento é estável entre sementes, no tempo e entre métodos — ou não;
- que a rede supera PCA, Mahalanobis e Isolation Forest — ou não, e isso é
  publicável nas duas direções;
- que os indicadores prudenciais adaptados carregam mais informação que a
  transposição direta dos modelos de empresa não financeira — ou não;
- quanto da performance de um desenho supervisionado neste domínio vem de
  circularidade.

**Não poderá:**

- afirmar que qualquer instituição cometeu fraude ou irregularidade;
- tratar o escore como prova, indício jurídico ou opinião de auditoria;
- inferir causalidade entre indicador e conduta;
- generalizar para fora de S2/S3 ou fora de 2019–2024.

A conclusão defensável tem esta forma: *modelos não lineares aplicados a dados
públicos do IF.data/COSIF produzem uma ordenação de risco que concentra, nas
primeiras posições, instituições com características contábeis que a literatura
associa a maior probabilidade de manipulação — oferecendo à auditoria um
critério de priorização que os modelos lineares tradicionais, calibrados para
empresas não financeiras, não fornecem para este segmento.*

---

## 9. Índice da documentação

| Documento | Conteúdo |
|---|---|
| `README.md` | Visão geral e início rápido |
| `HISTORICO.md` | Decisões metodológicas; Apêndice A com observações sobre o texto |
| `docs/DOCUMENTACAO_MODULOS.md` | Cada módulo: entrada, saída, cálculo, decisão embutida |
| `docs/ESPECIFICACAO_TRATAMENTO.md` | Ajustes no código e as 21 fórmulas |
| `docs/GUIA_EXTRACAO_MANUAL.md` | Obtenção dos dados, rota automática e manual |
| `docs/TESTE_CONTINUIDADE_2025.md` | O teste que fundamenta o corte em 2024 |
| `docs/FONTES_COMPLEMENTARES.md` | Fontes oficiais para cruzamento |
| `docs/SINTESE_DO_PROJETO.md` | Este documento |
