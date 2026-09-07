# Teste de continuidade do leiaute do IF.data em 2025

Registro do teste empírico que fundamenta a decisão de **encerrar o recorte
amostral em dezembro de 2024**, e não estendê-lo a 2025.

Documento destinado a anexo do TCC: transforma o corte temporal de escolha de
conveniência em decisão metodológica fundamentada.

---

## 1. O que motivou o teste

A partir de 2025 o IF.data passou a publicar os dados em seção própria
("Dados a partir de 2025"), com conjunto de relatórios distinto. A comparação
dos cabeçalhos do relatório Resumo confirmou alteração:

| 2024-12 (20 colunas) | 2025-03 (21 colunas) |
|---|---|
| `Carteira de Crédito Classificada` | `Carteira de Crédito` |
| `Passivo Circulante e Exigível a Longo Prazo e Resultados de Exercícios Futuros` | `Passivo Exigível` |
| — | `Títulos e Valores Mobiliários` *(nova)* |

As outras 18 colunas permanecem idênticas, na mesma ordem.

Renomeação de rótulo é inócua; **redefinição de conta não é**. Se a composição
da conta mudou, a série ganha descontinuidade estrutural no primeiro trimestre
de 2025 — e um modelo de detecção de anomalia leria isso como atipicidade
simultânea em todas as instituições, produzindo achado falso sem gerar erro.

---

## 2. Desenho do teste

Comparar a magnitude da variação trimestral **sob leiaute constante** com a
variação **na transição de leiaute**. Se forem equivalentes, a mudança é
nominal; se a segunda for maior, houve redefinição.

Métrica: razão da conta sobre o ativo total, por instituição. A razão neutraliza
crescimento de balanço e permite comparar trimestres.

| Transição | Leiaute | Papel |
|---|---|---|
| 2024-09 → 2024-12 | constante | contrafactual (variação normal) |
| 2024-12 → 2025-03 | alterado | transição sob suspeita |

Amostra: 1.344 e 1.349 instituições presentes em ambos os trimestres de cada
par (todas as instituições do IF.data, não apenas S2/S3, para maximizar poder).

---

## 3. Resultados

### 3.1 Carteira de crédito

| Estatística de \|Δ(carteira/ativo)\| | 2024-09→12 (constante) | 2024-12→2025-03 (alterado) | Razão |
|---|---|---|---|
| Mediana | 0,0127 | 0,0227 | **1,8×** |
| Percentil 90 | 0,0603 | 0,1117 | **1,9×** |
| Proporção acima de 0,05 | 13,5% | 27,9% | **2,1×** |
| Proporção acima de 0,10 | 4,9% | 11,7% | **2,4×** |

### 3.2 Passivo exigível

| Estatística de \|Δ(passivo/ativo)\| | 2024-09→12 (constante) | 2024-12→2025-03 (alterado) | Razão |
|---|---|---|---|
| Mediana | 0,0093 | 0,0098 | 1,05× |
| Proporção acima de 0,05 | 15,7% | 16,5% | 1,05× |

### 3.3 Comportamento no agregado

A mediana da razão carteira/ativo praticamente não se moveu: 0,4846 em 2024-12
contra 0,4774 em 2025-03. O deslocamento agregado é pequeno **porque as
reclassificações individuais se compensam entre si** — o que torna a estatística
agregada enganosa e justifica o exame em nível de instituição.

---

## 4. Conclusão

**`Passivo Exigível` é renomeação.** A variação na transição é indistinguível
da variação trimestral normal (razão 1,05× em ambas as métricas). A conta pode
ser tratada como continuidade da anterior.

**`Carteira de Crédito` é redefinição.** A dispersão individual dobra na
transição, em todas as métricas examinadas. A conta **não** é continuação
direta de `Carteira de Crédito Classificada`.

A diferença é economicamente inteligível: "carteira classificada" remete à
carteira sujeita à classificação de risco da Resolução CMN nº 2.682/1999
(níveis AA a H), enquanto "carteira de crédito" sem qualificação sugere
perímetro distinto. A verificação definitiva da composição de cada conta deve
ser feita no documento "Composição de Colunas" publicado pelo próprio IF.data
para cada leiaute.

---

## 5. Consequência para a pesquisa

A carteira de crédito é insumo de **quatro** dos dezessete indicadores:

| Indicador | Uso da carteira |
|---|---|
| `delta_carteira` | variação interanual sobre ativo médio |
| `sgi_bancario` | crescimento da carteira (análogo ao SGI de Beneish) |
| `intensidade_provisao` | provisão sobre carteira |
| `cobertura_provisao` | provisão sobre carteira em níveis E–H |

Emendar 2025 à série produziria, em todos esses indicadores, uma variação
espúria comum a todas as instituições — exatamente o padrão que o modelo é
treinado para sinalizar.

Há ainda um agravante temporal: os indicadores de variação comparam um
trimestre com o **mesmo trimestre do ano anterior**. Para 2025-03, a
comparação seria com 2024-03, que está no leiaute antigo. Toda a variação
interanual de 2025 estaria contaminada, e só em 2026 haveria quatro trimestres
consecutivos sob o novo leiaute.

### Decisão adotada

**Recorte mantido em 2019-03 a 2024-12 (24 trimestres).**

O corte deixa de ser escolha de conveniência e passa a ter fundamento
verificável: há descontinuidade documentada na definição da carteira de crédito
a partir de 2025-03, e a comparabilidade da série exige leiaute constante.

### Alternativa descartada

Usar 2025 como conjunto de validação externa (*holdout*). Descartada porque os
indicadores de variação interanual de 2025 dependem de 2024, atravessando a
quebra. Um *holdout* contaminado é pior que nenhum: produziria métrica de
generalização que mede efeito de mudança contábil.

### Reavaliação futura

Com quatro trimestres consecutivos sob o leiaute vigente (2025-03 a 2025-12),
torna-se possível construir variação interanual internamente consistente a
partir de 2026-03. Uma extensão do estudo pode então tratar o período pós-2025
como painel independente, com normalização própria, e comparar os padrões
detectados nos dois regimes.

---

## 6. Observações laterais

**Composição da amostra ao longo do tempo.** Os segmentos alvo cresceram no
período:

| Data-base | S2 | S3 | Total S2+S3 |
|---|---|---|---|
| 2019-03 | 6 | 42 | 48 |
| 2025-03 | 9 | 58 | 67 |

Compatível com a expansão de bancos digitais e instituições de médio porte
observada no período, e útil como estatística descritiva.

**Conta nova sem retroação.** `Títulos e Valores Mobiliários` aparece em 2025
(mediana de 8,9% do ativo). Corresponde ao conceito `tvm` do estudo, análogo
funcional do estoque nos modelos de Dechow et al. (2011). Por existir apenas a
partir de 2025, não pode integrar o painel principal — o indicador `delta_tvm`
permanece dependente do relatório Ativo.

---

## 7. Reprodutibilidade

Arquivos utilizados, todos do relatório Resumo, tipo de instituição
"Conglomerados Prudenciais e Instituições Independentes":

- `dados_202409_Resumo.csv`
- `dados_202412_Resumo.csv`
- `dados_202503_Resumo.csv`

O teste é reproduzível com `ifdata.carregar_ifdata_csv()` seguido do cálculo
das razões e da comparação das distribuições de variação absoluta, conforme
descrito na seção 2.
