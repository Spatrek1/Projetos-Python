# Especificação do tratamento e dos cálculos

Registro do tratamento aplicado à base `IF DATA BASE` (144 arquivos, 24
trimestres × 6 relatórios, 2019-03 a 2024-12) e da especificação de cada
indicador construído.

Princípio observado em todo o processo: **nenhum valor foi criado, imputado ou
alterado**. Conta ausente permanece ausente e é reportada.

---

## 1. Ajustes realizados no código

### 1.1 Cabeçalho hierárquico — a correção mais importante

As exportações do IF.data usam **de uma a três linhas de cabeçalho**: a
primeira traz os grupos sintéticos, as seguintes detalham as contas analíticas.
O leitor anterior lia apenas a primeira linha, o que produzia dois defeitos
simultâneos: perdia as contas analíticas e tratava as demais linhas de
cabeçalho como se fossem instituições.

| Relatório | Linhas de cabeçalho |
|---|---|
| Resumo, Segmentação | 1 |
| Ativo | 2 |
| DRE, Passivo, Informações de Capital | 3 |

As contas que só existem no segundo e terceiro níveis são justamente as que
sustentam os indicadores prudenciais do estudo:

- `Provisão sobre Operações de Crédito (d2)` — nível 2 do Ativo
- `Resultado de Provisão para Créditos de Difícil Liquidação (b5)` — nível 3 da DRE
- `Rendas de Prestação de Serviços (d1)`, `Despesas de Pessoal (d3)`,
  `Despesas Administrativas (d4)` — nível 2 da DRE

**Solução.** A primeira linha de dados é identificada pelo código da
instituição na segunda coluna (inteiro de seis ou mais dígitos); tudo acima é
cabeçalho, e o nome de cada coluna passa a ser o rótulo do nível mais profundo
preenchido.

**Validação.** A identidade contábil fecha exatamente no caso do Itaú em
2024-03: `741.455.019 + (−48.436.033) = 693.018.986`, isto é, Operações de
Crédito mais Provisão igual a Operações Líquidas de Provisão.

### 1.2 Coalescência de variantes de rótulo

Os rótulos mudam ao longo do recorte quando o BCB acrescenta parcelas ao
cálculo. O RWA, por exemplo, passa de `(i) = (f) + (g) + (h)` para
`(j) = (f) + (g) + (h) + (i)` com a inclusão do RWAsp.

São variantes do **mesmo** conceito e nunca coexistem no mesmo trimestre.
Antes da correção, `patrimonio_liquido` aparecia com 74% de ausência porque
`Patrimônio Líquido (i)` cobre 6 trimestres e `Patrimônio Líquido (j)` cobre
os outros 18. Após a coalescência, a ausência caiu para 0,27%.

Distinção implementada e deliberada:

- **Soma** entre parcelas semanticamente distintas do mesmo conceito
  (disponibilidades = caixa + aplicações interfinanceiras), com `min_count=1`
  para que linha sem nenhuma parcela permaneça ausente em vez de virar zero;
- **Coalescência** entre variantes de rótulo, preenchendo apenas onde a
  principal está ausente. Somá-las duplicaria o valor.

### 1.3 Mapeamento explícito em vez de reconhecimento por padrão

O mapeamento passou a nomear cada conta expressamente. No relatório Ativo
coexistem `Operações de Crédito (d1)`, `Provisão sobre Operações de Crédito
(d2)` e `Operações de Crédito Líquidas de Provisão (d)` — um casamento
aproximado por expressão regular poderia escolher qualquer uma das três.

### 1.4 Conversão numérica

O CSV do IF.data usa convenção brasileira com percentuais sufixados:

| Formato no arquivo | Convertido para |
|---|---|
| `1.516.147.949` | `1516147949.0` (ponto é separador de milhar) |
| `19,26%` | `19.26` |
| `NA`, `NA%` | ausente |

### 1.5 Remoção do rodapé de legenda

Cada exportação anexa ao final um bloco com a legenda dos códigos (TCB, SR, TD,
TC) e os **totais agregados** de cada categoria. Mantidas, essas linhas
entrariam no painel como instituições de trilhões em ativo. São separadas pela
ausência de código e preservadas em `df.attrs["legenda"]`.

### 1.6 Tolerância a variações no nome dos arquivos

A base traz `Info de Cap`, `Info de cap`, `Info cap` e `Info Cap` para o mesmo
relatório, e `2019-9` em lugar de `2019-09`. O identificador normaliza acentos
e caixa, e aceita mês com um ou dois dígitos.

---

## 2. Problema encontrado na base

**`dados 2020-06 Resumo.csv` contém o relatório Segmentação, não o Resumo.**

Verificado por assinatura de conteúdo: o arquivo traz as colunas
`Instituição Sujeita à Apuração da Exposição Total` e
`Exposição Total ou Ativo Total (R$ mil)`, características da Segmentação, e
não traz `Carteira de Crédito Classificada`.

**Consequência.** Os conceitos exclusivos do Resumo ficam ausentes em 2020-06:
`carteira_classificada`, `numero_agencias` e `exposicao_total` aparecem com
cerca de 4% de ausência (1 trimestre em 24). O indicador
`discrepancia_carteira` fica indefinido nessa data-base e, por depender de
comparação interanual em outros indicadores, o efeito se propaga.

**Correção necessária.** Rebaixar o relatório Resumo de 06/2020 no IF.data e
substituir o arquivo. O restante da base está íntegro.

---

## 3. Os seis parâmetros contábeis obrigatórios

Origem exata de cada um, conforme rótulo real das exportações:

| Conceito | Relatório | Coluna no IF.data | Nível |
|---|---|---|---|
| `ativo_total` | ativo | Ativo Total (k) = (i) - (j) | 2 |
| `carteira_credito` | ativo | Operações de Crédito (d1) | 2 |
| `provisao_pcld` | ativo | Provisão sobre Operações de Crédito (d2) | 2 |
| `patrimonio_liquido` | passivo | Patrimônio Líquido (i) | 3 |
| `resultado_intermediacao` | dre | Resultado de Intermediação Financeira (c) = (a) + (b) | 3 |
| `lucro_liquido` | dre | Lucro Líquido (j) = (g) + (h) + (i) | 3 |

**Cobertura obtida:** 31.732 de 31.819 observações (99,73%) para os seis. As 87
ausências correspondem a instituições que constam do cadastro sem apresentar
demonstração naquele trimestre.

Observação sobre `provisao_pcld`: é publicada com **sinal negativo**, o que
permite que a identidade contábil se feche por soma. Todo indicador que exige
magnitude aplica valor absoluto de forma explícita.

---

## 4. Conceitos mapeados por relatório


### ativo (10 conceitos)

| Conceito | Coluna(s) de origem |
|---|---|
| `ativo_total` | Ativo Total (k) = (i) - (j) |
| `ativo_total_ajustado` | Ativo Total Ajustado (i) = (a) + (b) + (c) + (d) + (e) + (f) + (g) + (h) |
| `disponibilidades` | Disponibilidades (a) + Aplicações Interfinanceiras de Liquidez (b) |
| `tvm` | TVM e Instrumentos Financeiros Derivativos (c) |
| `carteira_credito` | Operações de Crédito (d1) |
| `provisao_pcld` | Provisão sobre Operações de Crédito (d2) |
| `carteira_liquida` | Operações de Crédito Líquidas de Provisão (d) |
| `arrendamento` | Arrendamento Mercantil Líquido de Provisão (e) |
| `outros_creditos` | Outros Créditos - Líquido de Provisão (f) + Outros Ativos Realizáveis (g) |
| `permanente` | Permanente Ajustado (h) |

### dre (18 conceitos)

| Conceito | Coluna(s) de origem |
|---|---|
| `rendas_credito` | Rendas de Operações de Crédito (a1) |
| `rendas_tvm` | Rendas de Operações com TVM (a3) |
| `receita_intermediacao` | Receitas de Intermediação Financeira (a) = (a1) + (a2) + (a3) + (a4) + (a5) + (a6) |
| `despesa_captacao` | Despesas de Captação (b1) |
| `despesa_provisao` | Resultado de Provisão para Créditos de Difícil Liquidação (b5) |
| `despesa_intermediacao` | Despesas de Intermediação Financeira (b) = (b1) + (b2) + (b3) + (b4) + (b5) |
| `resultado_intermediacao` | Resultado de Intermediação Financeira (c) = (a) + (b) |
| `receita_servicos` | Rendas de Prestação de Serviços (d1) + Rendas de Tarifas Bancárias (d2) |
| `despesa_pessoal` | Despesas de Pessoal (d3) |
| `despesa_administrativa` | Despesas Administrativas (d4) |
| `despesa_tributaria` | Despesas Tributárias (d5) |
| `outras_receitas_op` | Outras Receitas Operacionais (d7) |
| `outras_despesas_op` | Outras Despesas Operacionais (d8) |
| `resultado_operacional` | Resultado Operacional (e) = (c) + (d) |
| `resultado_nao_operacional` | Resultado Não Operacional (f) |
| `resultado_antes_trib` | Resultado antes da Tributação, Lucro e Participação (g) = (e) + (f) |
| `ir_csll` | Imposto de Renda e Contribuição Social (h) |
| `lucro_liquido` | Lucro Líquido (j) = (g) + (h) + (i) |

### info_cap (8 conceitos)

| Conceito | Coluna(s) de origem |
|---|---|
| `capital_principal` | Capital Principal para Comparação com RWA (a) |
| `patrimonio_referencia` | Patrimônio de Referência para Comparação com o RWA |
| `rwa` | Ativos Ponderados pelo Risco (RWA) (j) = (f) + (g) + (h) + (i) |
| `rwa_credito` | RWA para Risco de Crédito (f) |
| `indice_basileia` | Índice de Basileia (n) = (e) / (j) |
| `indice_capital_principal` | Índice de Capital Principal (l) = (a) / (j) |
| `adicional_capital` | Adicional de Capital Principal |
| `indice_imobilizacao` | Índice de Imobilização (p) |

### passivo (12 conceitos)

| Conceito | Coluna(s) de origem |
|---|---|
| `depositos_vista` | Depósitos à Vista (a1) |
| `depositos_prazo` | Depósitos a Prazo (a4) |
| `depositos_total` | Depósito Total (a) |
| `compromissadas` | Obrigações por Operações Compromissadas (b) |
| `letras_financeiras` | Letras Financeiras (c3) |
| `captacoes` | Captações (e) = (a) + (b) + (c) + (d) |
| `depositos_outros` | Depósitos Outros (a6) |
| `passivo_total` | Passivo Total (k) = (h) + (i) + (j) + Passivo Total (j) = (h) + (i) |
| `resultados_exerc_futuros` | Resultados de Exercícios Futuros (i) |
| `outras_obrigacoes` | Outras Obrigações (g) |
| `passivo_exigivel` | Passivo Circulante e Exigível a Longo Prazo (h) = (e) + (f) + (g) |
| `patrimonio_liquido` | Patrimônio Líquido (i) |

### resumo (2 conceitos)

| Conceito | Coluna(s) de origem |
|---|---|
| `carteira_classificada` | Carteira de Crédito Classificada |
| `numero_agencias` | Número de Agências |

### segmentacao (2 conceitos)

| Conceito | Coluna(s) de origem |
|---|---|
| `exposicao_total` | Exposição Total ou Ativo Total (R$ mil) |
| `ativos_exterior_usd` | Total de Ativos Consolidados no Exterior (US$ mil) |

---

## 5. Especificação dos indicadores

Notação: `Δ₄(x)` é a variação de `x` em relação ao **mesmo trimestre do ano
anterior**. A comparação é interanual, não trimestral, porque o balanço
bancário tem sazonalidade — dezembro concentra baixas e constituições — e a
diferença trimestral confundiria sazonalidade com anomalia.

`Ativo médio` é a média entre o ativo do trimestre e o do mesmo trimestre do
ano anterior; quando este não existe, usa-se o ativo corrente.

Divisão protegida: denominador nulo ou muito próximo de zero produz **ausente**,
nunca número. Denominador negativo em conta que deveria ser positiva também
produz ausente — inverteria a leitura do indicador.


### 5.1 Correspondência direta na literatura (1 indicadores)

**`delta_roa`** — Dechow et al. (2011) — CH_ROA

> ROA(t) − ROA(t−4), com ROA = Lucro líquido / Ativo médio

Aplicavel sem alteracao.

*Leitura de risco:* Queda de ROA aumenta a pressao por manipulacao (elemento 'pressao' do triangulo da fraude).


### 5.2 Adaptação por analogia funcional (9 indicadores)

**`soft_assets`** — Dechow et al. (2011) — SOFT_ASSETS

> (Ativo total − Disponibilidades − Permanente) / Ativo total

Conceito transporta bem para banco: mede a fracao do ativo cuja mensuracao depende de estimativa e julgamento. 'Disponibilidades' soma caixa e aplicacoes interfinanceiras de liquidez.

*Leitura de risco:* Quanto maior, maior a discricionariedade contabil disponivel.

**`delta_carteira`** — Dechow et al. (2011) — CH_REC

> Δ₄(Carteira de crédito) / Ativo médio

Recebiveis em banco correspondem a carteira de credito bruta, antes da provisao.

*Leitura de risco:* Crescimento acelerado sem provisao correspondente e sinal de risco.

**`delta_tvm`** — Dechow et al. (2011) — CH_INV

> Δ₄(TVM) / Ativo médio

Nao existe estoque em banco. Substituido por titulos e valores mobiliarios, ativo de giro sujeito a mensuracao por valor justo.

*Leitura de risco:* Variacao brusca pode indicar reclassificacao entre categorias de TVM.

**`accrual_bancario`** — Dechow et al. (2011) — RSST_ACC / Beneish — TATA

> (Lucro líquido − proxy de caixa) / Ativo médio, com proxy de caixa = Lucro líquido + |Despesa de provisão| − Δ₄(Outros créditos)

O IF.data nao publica demonstracao dos fluxos de caixa. O proxy soma de volta a despesa de provisao — item sem efeito caixa no periodo — e desconta a variacao de creditos operacionais. E APROXIMACAO DECLARADA.

*Leitura de risco:* Accrual alto e persistente indica resultado sustentado por competencia, nao por caixa.

**`gmi_bancario`** — Beneish (1999) — GMI

> NIM(t−4) / NIM(t), com NIM = Resultado de intermediação / Ativo médio

Margem bruta substituida pela margem financeira liquida (NIM), que cumpre a mesma funcao economica em banco.

*Leitura de risco:* GMI > 1 indica deterioracao de margem — pressao por compensar no resultado.

**`sgi_bancario`** — Beneish (1999) — SGI

> Carteira de crédito(t) / Carteira de crédito(t−4)

Crescimento de vendas substituido por crescimento da carteira de credito.

*Leitura de risco:* Crescimento acelerado e o preditor isolado mais recorrente em episodios de quebra bancaria; e tambem o instrumento GROWTH de Benyasrisawat e Ounlert (2026).

**`aqi_bancario`** — Beneish (1999) — AQI

> (Outros créditos + Permanente) / Ativo total

Qualidade do ativo medida pela participacao de ativos de realizacao incerta. O IF.data nao separa intangivel nem creditos tributarios: ambos estao dentro de 'Permanente Ajustado'.

*Leitura de risco:* Elevacao indica migracao do balanco para ativos de mensuracao frouxa.

**`levi_bancario`** — Beneish (1999) — LEVI

> Ativo total / Patrimônio líquido

Alavancagem contabil. Complementada pelo indice de Basileia, que e a medida prudencial pertinente.

*Leitura de risco:* Alavancagem crescente com Basileia caindo e a configuracao de maior pressao.

**`sgai_bancario`** — Beneish (1999) — SGAI

> (|Despesa de pessoal| + |Despesa administrativa|) / (Resultado de intermediação + Receita de serviços)

Indice de eficiencia operacional bancaria. Despesas vem com sinal negativo no IF.data; aplica-se valor absoluto.

*Leitura de risco:* Deterioracao da eficiencia aumenta pressao sobre o resultado.


### 5.3 Proposições a partir do arcabouço prudencial (9 indicadores)

**`cobertura_provisao`** — Proposto — Res. CMN 2.682/1999

> |Provisão sobre operações de crédito| / Carteira de crédito bruta

O IF.data nao publica a carteira por nivel de risco (AA-H) nos relatorios do recorte. A cobertura e medida sobre a carteira bruta, nao sobre a carteira E-H. E medida menos sensivel: capta o nivel de provisionamento, nao sua suficiencia frente ao risco ja reconhecido.

*Leitura de risco:* Queda da cobertura sem melhora correspondente de qualidade da carteira e o padrao esperado de subprovisionamento.

**`intensidade_despesa_provisao`** — Proposto — Res. CMN 2.682/1999

> |Despesa de provisão do período| / Carteira média

Fluxo, nao estoque: mede quanto foi constituido no trimestre. Complementa a cobertura, que e saldo acumulado.

*Leitura de risco:* Reducao abrupta sem melhora de qualidade sugere resultado inflado por nao constituicao ou reversao de provisao.

**`descasamento_provisao`** — Proposto — supervisão prudencial

> Δ₄(Cobertura de provisão) − Δ₄(Carteira/Ativo)

Divergencia entre a evolucao do provisionamento e a da exposicao a credito. Substitui o descasamento provisao x inadimplencia, inviavel por ausencia do indice de inadimplencia no IF.data.

*Leitura de risco:* Carteira crescendo com cobertura caindo e o descasamento de maior interesse para o auditor.

**`folga_basileia`** — Proposto — arcabouço de Basileia (BCB)

> Índice de Basileia − piso regulatório de referência

Distancia ao minimo. O piso aplicavel varia por instituicao e por data com os adicionais de capital; usa-se piso fixo de referencia, registrado como ponto de correcao.

*Leitura de risco:* Folga pequena e persistente cria incentivo direto a gerenciar o RWA ou o resultado.

**`qualidade_capital`** — Proposto — arcabouço de Basileia (BCB)

> Capital principal / Patrimônio de referência

Fracao do capital regulatorio composta por capital principal, de maior capacidade de absorcao de perdas.

*Leitura de risco:* Queda indica capital sustentado por instrumentos de qualidade inferior.

**`dependencia_nao_recorrente`** — Proposto — qualidade do resultado

> |Resultado não operacional| / |Resultado antes da tributação|

Peso do resultado nao operacional na formacao do lucro.

*Leitura de risco:* Resultado concentrado em linha nao recorrente e sinal classico de qualidade baixa de lucro.

**`carga_tributaria_efetiva`** — Proposto — qualidade do resultado

> |IR e CSLL| / |Resultado antes da tributação|

Carga efetiva sobre o resultado. Sem correspondente nos modelos de origem, mas classica em analise forense: divergencia persistente entre carga efetiva e nominal sinaliza diferencas entre lucro contabil e fiscal.

*Leitura de risco:* Carga muito abaixo da nominal, de forma persistente, merece exame.

**`concentracao_captacao`** — Proposto — risco de liquidez

> Depósitos a prazo / Captações totais

Composicao da captacao. Deposito a prazo e a fonte mais sensivel a percepcao de risco pelo mercado.

*Leitura de risco:* Concentracao elevada aumenta a vulnerabilidade a corrida de saques.

**`discrepancia_carteira`** — Proposto — consistência entre relatórios

> (Carteira classificada − Carteira contábil) / Carteira contábil

O IF.data publica a carteira em dois relatorios com definicoes distintas: 'Carteira de Credito Classificada' no Resumo e 'Operacoes de Credito' no Ativo. A divergencia entre elas e informacao, nao ruido.

*Leitura de risco:* Divergencia atipica entre as duas medidas sugere diferenca entre o que foi classificado para fins de risco e o que foi registrado contabilmente.


---

## 6. Resultado do tratamento

| Etapa | Resultado |
|---|---|
| Arquivos lidos | 143 de 144 (1 divergente, ver seção 2) |
| Observações no painel completo | 31.819 |
| Instituições distintas | 1.629 |
| Trimestres | 24 (2019-03 a 2024-12) |
| Conceitos construídos | 52 |
| **Amostra S2/S3** | **1.347 observações, 72 instituições** |
| Indicadores construídos | 19 de 19 |

Composição da amostra: 9 instituições em S2 (154 observações) e 66 em S3
(1.193 observações), somando as que entraram e saíram do segmento ao longo do
recorte.

A segmentação vem da coluna `SR` dos próprios relatórios — é a classificação
oficial do supervisor, conforme Resolução CMN nº 4.553/2017, e dispensa a
reconstrução pela razão Exposição/PIB.

---

## 7. Pontos de atenção nos resultados

Alguns indicadores apresentam valores extremos, todos com a mesma origem:
**denominador próximo de zero**. Não são erros de cálculo, e não foram
alterados.

| Indicador | Amplitude observada | Origem do extremo |
|---|---|---|
| `gmi_bancario` | −146 a 2.485 | NIM próxima de zero no denominador |
| `sgai_bancario` | −1.715 a 10.213 | Receita operacional próxima de zero |
| `carga_tributaria_efetiva` | 0 a 139 | Resultado antes da tributação próximo de zero |
| `sgi_bancario` | 0 a 160 | Instituições em início de operação |

O tratamento previsto no painel — winsorização a 1% e 99% **dentro de cada
trimestre**, seguida de padronização por mediana e desvio absoluto mediano
dentro de (segmento, trimestre) — absorve esses extremos sem descartar
observações. A winsorização por trimestre, e não global, preserva a comparação
transversal, já que as contas mudam de escala ao longo do período.

Registro para o TCC: `folga_basileia` tem mínimo de −1,46, indicando pelo menos
uma instituição-trimestre abaixo do piso de referência de 10,5%. A verificação
do requerimento efetivamente aplicável a essa instituição naquela data-base é
ponto de correção aberto.

