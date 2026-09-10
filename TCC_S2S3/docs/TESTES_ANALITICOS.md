# Os seis testes analíticos

Um teste por parâmetro contábil obrigatório. São procedimentos analíticos no
sentido da auditoria: comparam o valor registrado com uma expectativa formada a
partir dos pares e do histórico da própria instituição.

Rodam em `processar_base.py`, junto com o tratamento. **Não dependem de treino,
partição, semente nem convergência** — qualquer terceiro que baixe a mesma base
do IF.data reproduz os números abaixo. É a diferença essencial em relação ao
escore da rede neural, e é o que os torna citáveis no TCC sem ressalva de
reprodutibilidade.

| Teste | Parâmetro âncora | Hipótese testada |
|---|---|---|
| T1 | `provisao_pcld` | A provisão acompanha a exposição a risco de crédito |
| T2 | `carteira_credito` | O crescimento é compatível com pares, capital e provisão |
| T3 | `ativo_total` | A composição não migra para contas de mensuração discricionária |
| T4 | `patrimonio_liquido` | A alavancagem é compatível com os pares e a folga de capital é adequada |
| T5 | `resultado_intermediacao` | A margem é compatível com a carteira e com os pares |
| T6 | `lucro_liquido` | O lucro é sustentado por operação recorrente |

## Resultado sobre a base tratada

1.347 observações, 72 instituições, 24 trimestres. Limiar de 2,5 desvios (MAD)
frente aos pares do mesmo segmento e trimestre.

| Teste | Observações | Instituições | % do painel |
|---|---:|---:|---:|
| T1 Suficiência de provisão (PCLD) | 76 | 10 | 5,6 |
| T2 Crescimento da carteira | 62 | 22 | 4,6 |
| T3 Composição e opacidade do ativo | 199 | 17 | 14,8 |
| T4 Alavancagem e adequação de capital | 110 | 18 | 8,2 |
| T5 Margem financeira | 136 | 29 | 10,1 |
| T6 Qualidade do resultado | 326 | 50 | 24,2 |

## O limiar é calibração, não significância

Sob normalidade, 2,5 desvios corresponderiam a cerca de 1% em cada cauda. **Não
é o que ocorre nesta base.** Os indicadores são razões contábeis de cauda pesada
e, em vários casos, concentradas em zero, de modo que o MAD é pequeno frente à
cauda. A taxa observada é várias vezes a nominal.

Não é defeito a corrigir: é característica da distribuição, e o relato honesto
consiste em reportar o limiar adotado junto com a taxa que ele produz.

| Limiar | T1 | T2 | T3 | T4 | T5 | T6 | ao menos um |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2,0 | 6,8 | 5,9 | 17,6 | 10,3 | 16,0 | 29,3 | 55,7 |
| 2,5 | 5,6 | 4,6 | 14,8 | 8,2 | 10,1 | 24,2 | 46,8 |
| 3,0 | 4,2 | 3,5 | 11,9 | 6,8 | 7,3 | 20,3 | 38,4 |
| 3,5 | 3,1 | 2,8 | 9,1 | 5,3 | 5,2 | 16,9 | 31,6 |
| 4,0 | 2,3 | 2,3 | 6,2 | 4,4 | 3,9 | 14,6 | 26,4 |
| 5,0 | 1,3 | 1,8 | 3,2 | 3,2 | 1,8 | 10,9 | 18,9 |

Gerada por `testes_analiticos.sensibilidade()`. Toda condição corroborante está
atrelada ao limiar declarado (`FRACAO_CORROBORACAO = 0,6`) — sem isso a taxa
ficaria insensível ao parâmetro e esta tabela não teria conteúdo.

## Três decisões metodológicas que mudam o resultado

### 1. Escala logarítmica em T1

A cobertura de provisão é limitada em zero à esquerda e ilimitada à direita. Na
escala simétrica em MAD, cobertura **exatamente zero** — a subprovisão máxima
possível — dista apenas cerca de 2,1 desvios da mediana dos pares, enquanto a
cauda direita alcança mais de 14. Nenhum limiar usual alcançaria a condição que
o teste existe para detectar: com o critério simétrico, T1 sinalizava 13
observações de **uma única** instituição.

Em log a comparação passa a ser multiplicativa — "um terço da mediana dos pares"
pesa tanto quanto "o triplo" —, que é a leitura correta para uma razão.

### 2. Provisão zero é condição categórica

69 observações de 8 instituições registram carteira de crédito viva — mediana de
R$ 767 mil, máximo de R$ 3,07 bilhões — com provisão **exatamente zero**. Isso
não é cauda de distribuição e não deve ser submetido a limiar: T1 sinaliza
diretamente.

Pode ser carteira integralmente classificada em AA, que a Res. CMN 2.682/1999
dispensa de provisionamento, ou falha de preenchimento do informe. A distinção
exige consultar a composição por nível de risco — está apontada em
`pontos_de_correcao.csv`.

### 3. A segmentação S2/S3 não controla modelo de negócio

**Este é o achado mais relevante para o TCC.** Aplicado sem ressalva, T1
sinalizava quase exclusivamente bancos de atacado e de investimento — Morgan
Stanley, MUFG, Sumitomo, Citibank, Deutsche, Crédit Agricole, BofA, Goldman
Sachs, JP Morgan — e a corretora XP. Provisionar pouco é o modelo de negócio
dessas instituições, não uma anomalia contábil.

A causa é estrutural: a Res. CMN 4.553/2017 ordena as instituições por **porte e
relevância sistêmica**, não por natureza da carteira. Banco de atacado e
cooperativa de varejo dividem o mesmo grupo de comparação. O código TCB também
não resolve — Citibank, Deutsche e os bancos de varejo são todos `b1`, e
refinar o grupo por TCB produz células de 1 a 3 instituições, pequenas demais
para estimar mediana e MAD.

A solução não inventa classificação alguma. Usa uma grandeza que a própria base
fornece — a participação do crédito no ativo (`peso_carteira`):

| Grupo | Mediana de crédito/ativo | Fração com crédito < 10% do ativo |
|---|---:|---:|
| Bancos de atacado e investimento | 4,9% | 81% |
| Demais instituições | 36,3% | 22% |

Abaixo de 10% o crédito é parcela imaterial do balanço e a cobertura de provisão
deixa de ser grandeza comparável à de uma instituição de varejo. T1 e T2 passam
a se aplicar apenas onde o crédito é material — condição de **materialidade**,
não de limiar, e a mesma lógica que uma equipe de auditoria aplicaria.

## Sinalização estrutural não é evento

A comparação com os pares mede **nível**, e nível persistentemente distinto
reflete o modelo de negócio, não uma ocorrência. Uma instituição que destoa em 2
de 24 trimestres oferece uma pergunta datada, confrontável com fatos do período.
Uma que destoa em 24 de 24 oferece apenas a constatação de que opera em outro
segmento de mercado.

`classificar_persistencia()` separa as duas situações, e `foco_de_exame()` retém
apenas a sinalização episódica:

| | Observações com ao menos um teste | Instituições | Marcações somadas |
|---|---:|---:|---:|
| Todas as sinalizações | 630 | 60 | 909 |
| Foco de exame (exclui estrutural) | 449 | 59 | 540 |

Para T1, o filtro reduz de 76 observações para **31, em 8 instituições** — todas
em trimestres em que a instituição de fato mantinha carteira material. É a carga
que uma equipe de auditoria consegue examinar.

## Saída

Gravados em `dados/tratados/` por `processar_base.py`:

| Arquivo | Conteúdo |
|---|---|
| `testes_analiticos_sinalizacoes.csv` | uma linha por (instituição, trimestre), com o desvio medido e a marcação de cada teste |
| `testes_analiticos_foco_de_exame.csv` | apenas a sinalização episódica |
| `testes_analiticos_resumo.csv` | a contagem por teste |
| `testes_analiticos_persistencia.csv` | classificação estrutural / intermitente / pontual |
| `testes_analiticos_sensibilidade.csv` | taxa por limiar |
| `quadro_testes_analiticos.csv` | o quadro dos seis testes, para anexo do TCC |

`detalhar(sinal, cod_inst, anomes)` produz o texto auditável de uma observação:
hipótese testada, critério, desvio medido e o procedimento de auditoria cabível.

## Como reportar no TCC

Nomear o resultado como **"observações sinalizadas para exame"**, nunca como
"instituições com indício de fraude". A sinalização é divergência frente ao
comportamento dos pares — hipótese a examinar, não conclusão. Mudança de modelo
de negócio, incorporação e alteração de política contábil produzem exatamente o
mesmo sintoma, e a seção anterior mostra que, nesta base, com frequência é o que
está acontecendo.

Reportar sempre: o limiar adotado, a taxa de sinalização resultante e a tabela
de sensibilidade.

## Ponto que depende de decisão sua

O corte de materialidade em 10% do ativo é defensável e está sustentado pela
tabela acima, mas é escolha. Convém rodar `sensibilidade()` também variando
`PESO_MINIMO_CARTEIRA` (em `testes_analiticos.py`) e registrar no texto que o
resultado de T1 e T2 é condicional a esse corte.

**Área designada:** `src/fraude_s2s3/testes_analiticos.py`,
constante `PESO_MINIMO_CARTEIRA`.
