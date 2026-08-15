# Histórico de desenvolvimento

Registro das decisões metodológicas tomadas na construção do pipeline, com a justificativa de
cada uma e as alternativas descartadas. O propósito é permitir que orientador e banca auditem o
percurso — não apenas o resultado — e que decisões possam ser revertidas com conhecimento do que
foi ponderado ao tomá-las.

Projeto de referência: *Auditorias em instituições financeiras dos segmentos S2 e S3*
(Fernando Ulerich Fonseca, Universidade Federal Fluminense).

---

## 1. Ponto de partida

O projeto de pesquisa propõe aplicar XGBoost e LightGBM a dados públicos do IF.data/COSIF para
identificar padrões anômalos indicativos de fraude contábil em instituições dos segmentos S2 e S3,
no período de 2019 a 2024, tendo como referência metodológica principal Benyasrisawat e Ounlert
(2026).

A demanda que originou este pipeline acrescentou um requisito: implementar uma **rede neural**,
coletando os dados via API e ajustando a arquitetura conforme as métricas fossem se estabelecendo.

Duas observações condicionaram tudo o que se seguiu.

**Primeira.** O artigo de referência não trabalha com instituições financeiras. Seus indicadores
(DF-Score e PF-Score) derivam de modelos calibrados em empresas não financeiras, e vários de seus
componentes não têm correspondente no balanço bancário. A adaptação, portanto, não é um ajuste de
implementação: é o conteúdo metodológico do trabalho.

**Segunda.** Não existe rótulo público de fraude para bancos brasileiros. Essa ausência não é
detalhe operacional — ela determina que classe de modelo é aplicável e que classe de afirmação o
trabalho pode sustentar ao final.

---

## 2. O problema do rótulo, e por que ele define a arquitetura

Um classificador supervisionado exige alvo. Sem fraude verificada e datada, restam três caminhos:

1. **Construir um rótulo a partir de fórmulas contábeis** (M-Score, DF-Score, F-Score) e treinar
   contra ele. É o caminho do artigo de referência.
2. **Usar eventos públicos** (liquidação extrajudicial, regime de administração especial,
   intervenção, processos sancionadores) como proxy de irregularidade.
3. **Abandonar a supervisão** e medir atipicidade — distância ao comportamento normal do conjunto.

O caminho 1 foi rejeitado como espinha dorsal pelas razões da seção 3. O caminho 2 é o mais forte
em valor probatório, mas produz pouquíssimos positivos: serve para *validar*, não para *treinar*.
O caminho 3 foi adotado como método principal.

Daí a escolha do **autoencoder**: ele dispensa rótulo. Aprende a variedade de comportamento normal
do conjunto e produz, como escore, o erro de reconstrução — a medida de quanto uma observação não
pertence a esse padrão. É a única família de modelo que responde à pergunta do trabalho com os
dados que existem, sem inventar o alvo.

Consequência que atravessa toda a redação do TCC: o que se mede é **atipicidade contábil**, não
fraude. A distinção é sustentada pela própria literatura citada — Dyck, Morse e Zingales (2020)
estimam que apenas cerca de um terço das fraudes corporativas é detectado, de modo que o conjunto
de instituições sem evento conhecido mistura instituições íntegras e irregularidades nunca vindas a
público. Nenhum modelo treinado nesses dados separa as duas coisas.

---

## 3. Circularidade no desenho de referência

Ao reconstruir o procedimento de Benyasrisawat e Ounlert (2026) constatou-se o seguinte:

- O DF-Score é definido, na Tabela 3 do artigo, como a soma de oito componentes: `RSST_ACC`,
  `CH_REC`, `CH_INV`, `SOFT_ASSETS`, `CH_CS`, `CH_CM`, `CH_ROA`, `CH_FCF`.
- O vetor de atributos usado para prever o DF-Score, descrito na seção 3.2.2, é composto **desses
  mesmos oito componentes**.
- As métricas reportadas na Tabela 5 acompanham o que esse desenho produz: acurácia de 0,995 e
  AUC-ROC de 0,999.

Um modelo que recebe as parcelas e prevê a soma não está detectando fraude; está reaprendendo uma
identidade aritmética. Isso **não invalida o artigo** — cujo objeto é a relação entre risco de
fraude e opinião de auditoria, estimada posteriormente por IV-2SLS, com o XGBoost servindo de
etapa intermediária de construção do índice. Invalida, sim, a leitura de que "AUC 0,999 demonstra
capacidade de detecção", e replicar o desenho sem essa observação transportaria o artefato para o
TCC.

A resposta implementada foi o módulo `vazamento.py`, com uma **guarda de circularidade** que:

- identifica atributos que são componentes algébricos do rótulo, inclusive através de derivações
  (`z_par_x` continua sendo `x` para este efeito);
- interrompe ou filtra o treino antes que a métrica seja produzida;
- audita empiricamente correlações de posto próximas de 1 com o rótulo, que denunciam vazamento
  não declarado.

O notebook executa deliberadamente **as duas versões** — com e sem os componentes — e reporta as
duas lado a lado. Em ensaio sobre painel artificial de verificação, a diferença observada foi de
AUC 0,97 para 0,60. A magnitude exata dependerá dos dados reais; o que importa é que essa
diferença passa a ser um **resultado do trabalho**: quantifica quanto da performance reportada em
desenhos desse tipo vem de circularidade e não de capacidade preditiva.

Esta é, na avaliação de quem escreveu o pipeline, a contribuição metodológica mais defensável que o
TCC pode oferecer — mais do que a troca de algoritmo.

---

## 4. Adaptação dos modelos ao balanço bancário

### 4.1 O que não transporta

| Componente original | Situação em banco |
|---|---|
| `CH_INV` (estoques) | Não existe |
| Margem bruta (GMI) | Não existe custo das mercadorias vendidas |
| Vendas (SGI, DSRI) | "Receita" não é operacional no mesmo sentido |
| Depreciação (DEPI) | Irrelevante frente ao tamanho do balanço |

### 4.2 Critério adotado: analogia funcional

Preservou-se a *intenção econômica* de cada componente e substituiu-se a conta pelo equivalente
bancário. Exemplos:

- `CH_REC` (recebíveis) → variação da **carteira de crédito** sobre ativo médio;
- `CH_INV` (estoques) → variação de **títulos e valores mobiliários**, ativo de giro sujeito a
  mensuração por valor justo;
- `GMI` (margem bruta) → razão entre margens financeiras (**NIM**) de períodos consecutivos;
- `SGI` (crescimento de vendas) → crescimento da carteira de crédito — que é também o instrumento
  `GROWTH` usado no artigo de referência;
- `AQI` (qualidade do ativo) → participação de ativos de realização incerta (outros créditos,
  intangível, **créditos tributários**) no ativo total;
- `SOFT_ASSETS` → transporta quase sem alteração, e continua medindo a fração do ativo cuja
  mensuração depende de julgamento.

### 4.3 Indicadores propostos, sem correspondente na literatura de origem

O balanço bancário oferece canais de manipulação que os modelos de empresa não financeira não
cobrem. Foram propostos, a partir do arcabouço prudencial (Resolução CMN 2.682/1999 e Basileia):

- **cobertura de provisão** — provisão sobre carteira classificada em níveis E–H;
- **intensidade de provisão** — despesa de provisão sobre carteira média;
- **descasamento provisão × inadimplência** — inadimplência subindo sem a provisão acompanhar;
- **peso do crédito tributário** no patrimônio líquido — capital sustentado por lucro futuro;
- **folga de Basileia** — distância ao mínimo regulatório;
- **dependência de resultado não recorrente**.

O subprovisionamento é o mecanismo mais direto de inflar resultado em instituição financeira, e não
é capturado por nenhum componente de Beneish, Dechow ou Piotroski.

**Ressalva registrada em código.** Esses indicadores não têm validação empírica prévia. Cada um
declara sua classe de evidência (`LIT` / `ADAP` / `PROP`) no catálogo do módulo `indicadores.py`, e
a função `alerta_evidencia()` gera o texto pronto para a seção de limitações. A distinção entre "o
que a literatura sustenta" e "o que eu propus" precisa estar visível no TCC, sob pena de a banca
interpretar proposição como achado consolidado.

### 4.4 Um teste que decide se a adaptação valeu a pena

Se o ranking de atributos que mais explicam a atipicidade (seção 12 do notebook) for dominado
pelos indicadores `PROP`, o trabalho tem argumento empírico de que **a adaptação ao contexto
bancário foi o que produziu informação** — e não a transposição dos modelos originais. Se for
dominado pelos `ADAP`, a conclusão é outra e igualmente publicável. O teste está implementado e
roda automaticamente.

---

## 5. Arquitetura e o problema do porte amostral

### 5.1 A restrição

S2 e S3 somam algo da ordem de dezenas de instituições. Com 24 trimestres, o painel fica na casa
de 10² a 10³ observações. É **pouco** para rede neural, e essa é a maior fragilidade prática do
desenho.

### 5.2 Decisões decorrentes

- Capacidade pequena por padrão (`64 → 32 → 8`), com `LayerNorm`, dropout e *weight decay*.
- Parada antecipada com paciência de 40 épocas.
- Escore final = **mediana sobre cinco sementes**, com a correlação de posto entre elas reportada
  como métrica de confiabilidade. Abaixo de ~0,80, o ranking depende mais da inicialização do que
  dos dados, e nenhuma instituição individual pode ser apontada.
- Monitoramento automático da razão parâmetros/observações, com pendência emitida quando extrapola.

### 5.3 Alternativa considerada e mantida desligada

Pré-treinar o autoencoder em instituições S4/S5 — muito mais numerosas — para aprender a variedade
de normalidade, e **pontuar apenas S2/S3**. Isso resolveria o porte amostral sem violar o escopo de
análise.

Mantida desligada (`Config.pretreino_fora_do_escopo = False`) porque o escopo declarado da pesquisa
é S2/S3 exclusivamente. A alteração muda o que se afirma sobre a fonte da "normalidade" aprendida e
é decisão do orientador, não de implementação.

### 5.4 Segunda arquitetura: quebra estrutural

Acrescentou-se um GRU que lê a janela de trimestres anteriores da instituição e prevê o seguinte.
O erro de previsão mede **mudança de comportamento** — mais próximo da intuição de auditoria
("passou a operar de outro jeito") do que a atipicidade transversal do autoencoder.

Os dois escores são complementares e reportados em separado: uma instituição pode ser sempre
diferente dos pares sem nunca mudar, ou mudar bruscamente permanecendo dentro do intervalo dos
pares.

---

## 6. Tratamento do painel

Quatro decisões, todas reversíveis e todas explícitas em `painel.py`:

1. **Winsorização por trimestre, não global.** Contas COSIF mudam de escala ao longo de 2019–2024;
   cortar caudas contra a distribuição do próprio trimestre preserva a comparação transversal.
2. **Z-score dentro de (segmento, trimestre), com mediana e MAD.** A pergunta é "esta instituição
   destoa dos pares *agora*?". Sem esse passo, o modelo aprende sobretudo tamanho e ciclo
   econômico. Mediana e MAD porque, com dezenas de instituições e caudas pesadas, a média é puxada
   pelo próprio caso extremo que se quer detectar.
3. **Normalização ajustada apenas no treino.** O contrário é vazamento, e é o erro mais comum em
   replicações deste tipo de trabalho.
4. **Ausentes marcados, não imputados pela média.** Cada atributo ganha coluna-sombra. Imputar a
   média faria a ausência parecer normalidade e reduziria o erro de reconstrução justamente onde há
   menos informação.

Sobre variações: adotou-se comparação **interanual** (quatro trimestres), não trimestre contra
trimestre. O balanço bancário tem sazonalidade — dezembro concentra baixas e constituições — e a
diferença trimestral confundiria sazonalidade com anomalia.

---

## 7. Partição temporal

O artigo de referência usa divisão 70/30 e validação cruzada em *k* dobras. Sobre **painel**, ambos
os procedimentos misturam trimestres futuros e passados da mesma instituição. Como indicadores
contábeis são altamente persistentes dentro da instituição, o modelo passa a "reconhecer a
instituição" em vez de generalizar, e a métrica fora da amostra fica otimista.

Adotou-se corte estritamente cronológico: treino até 2022, validação em 2023, teste em 2024. A
função `vazamento.auditar_particao_temporal()` verifica e bloqueia se houver sobreposição.

Sugestão para o TCC: rodar também o desenho aleatório e reportar a diferença. É evidência direta,
e barata, de um problema metodológico recorrente na literatura aplicada.

---

## 8. Avaliação sem rótulo

As métricas previstas no projeto de pesquisa (acurácia, AUC-ROC, recall, precisão) só existem
contra um rótulo. Sem ele, organizaram-se três formas de avaliação, em ordem decrescente de força
probatória:

**Primeira — validação por eventos públicos.** Eventos datados e verificáveis em fonte primária.
Duas cautelas de desenho foram incorporadas: trimestres *posteriores* ao evento são excluídos
(depois da intervenção o balanço reflete a intervenção, e acertar ali não é previsão), e a métrica
principal é **precisão no topo da lista**, não AUC-ROC — o auditor tem recurso finito e examinará
as *k* primeiras posições; AUC-ROC integra sobre faixas que ninguém examinaria.

**Segunda — coerência interna.** Estabilidade entre sementes, persistência trimestral do escore,
concordância com métodos alternativos. Não prova detecção, mas um escore instável não serve para
nada.

**Terceira — rótulo fraco.** Construído a partir dos próprios indicadores. Serve **apenas** para
comparar arquiteturas entre si, sob guarda de circularidade. O módulo emite pendência exigindo que
a métrica seja nomeada no texto como *"concordância com o rótulo fraco"*, nunca como *"detecção de
fraude"*.

---

## 9. Comparação obrigatória com métodos simples

Sem baseline, "a rede encontrou 12 instituições atípicas" é uma lista, não um resultado.

Implementaram-se PCA (erro de reconstrução linear), Mahalanobis com covariância robusta e Isolation
Forest, todos sobre o mesmo insumo e comparados em posto percentual — escores brutos de métodos
diferentes não são comparáveis.

A leitura tem duas saídas, ambas publicáveis: concordância alta com o PCA significa que a rede
redescobre o que um método linear já dizia, e o custo de interpretabilidade não se justifica;
concordância baixa exige explicar caso a caso o que a rede enxerga a mais. **A saída inaceitável é
não fazer a comparação.**

XGBoost e LightGBM permanecem, agora como termo de comparação e sob a guarda de circularidade.

---

## 10. Triangulação independente

Rede, PCA e Mahalanobis derivam do mesmo conjunto de indicadores. Se os três apontarem a mesma
instituição, isso não é corroboração — é a mesma medida contada três vezes.

Acrescentou-se conformidade à lei de Newcomb–Benford sobre os dígitos dos saldos publicados, que
independe de qualquer razão contábil construída aqui. Concordância entre escore alto de rede e não
conformidade a Benford é evidência genuinamente independente.

Três ressalvas implementadas como avisos automáticos: saldos do IF.data já são agregados, e a
conformidade é mais fraca em agregados; contas com piso, teto ou valor regulado violam a premissa
de escala livre; e desvio de Benford não é indício de fraude — arredondamento, conversão e
reclassificação produzem o mesmo sintoma.

---

## 11. Registro de pendências

A pedido do orientando, toda limitação encontrada durante a execução é registrada **no momento em
que aparece**, com área responsável e ação pedida, e consolidada ao final do notebook (seção 16).
Três níveis: `BLOQUEIA RESULTADO`, `COMPROMETE INTERPRETAÇÃO`, `OBSERVAÇÃO`.

A escolha de projeto relevante: um indicador que não pôde ser construído **não vira zero nem
`NaN` silencioso** — vira texto no relatório final. Ausência escondida é o modo mais comum de um
pipeline produzir números que ninguém consegue defender depois.

---

## 12. Verificação executada

- Dezesseis testes automatizados sobre o pipeline completo, todos passando.
- Notebook executado de ponta a ponta em modo de verificação: 49 células, zero erros.
- Confirmado que indicadores sem insumo são omitidos e reportados, nunca preenchidos com zero.
- Confirmado que a guarda de circularidade remove derivações (`z_par_`, `faltante_`) além dos
  componentes diretos.
- Confirmado que a partição temporal não apresenta sobreposição.

**Ressalva importante.** Estas verificações usaram um painel **artificial**
(`testes/fixture_fumaca.py`), gerado apenas para exercitar os caminhos de código. Nenhum número
dessas execuções é dado, e nenhum pode aparecer no TCC. O ambiente em que o pipeline foi
desenvolvido não tinha saída de rede para `bcb.gov.br` — a coleta real precisa ser executada na
máquina do pesquisador, e é por isso que a descoberta de esquema (seção 2 do notebook) foi
construída para confirmar o contrato da API em tempo de execução em vez de presumi-lo.

---

## Apêndice A — Observações sobre o texto do projeto de pesquisa

Levantadas durante a leitura para a construção do pipeline. Não são pontos de código; são pontos
que a banca provavelmente levantará.

**A.1 Título e método divergem.** O título — *"...com utilização de LLMs"* — e o cronograma
("detecção de fraudes via LLMs") anunciam modelos de linguagem, enquanto resumo, objetivos e
metodologia tratam de XGBoost e LightGBM, que não são LLMs. Três saídas coerentes: (i) ajustar o
título para *aprendizado de máquina* / *modelos não lineares*; (ii) incorporar de fato um componente
de LLM — o caminho natural seria análise textual de notas explicativas e pareceres de auditoria,
que o IF.data não fornece e exigiria outra fonte; (iii) manter LLM apenas como ferramenta de apoio
à redação, declarada como tal e fora do método. A opção (i) é a de menor risco.

**A.2 Atribuição incorreta na seção 2.4.** O texto afirma que Benyasrisawat e Ounlert combinaram
"variáveis do M-Score e do F-Score". O artigo trabalha com **DF-Score** (Dechow) e **PF-Score**
(Piotroski); o M-Score de Beneish não integra o desenho deles.

**A.3 Descrição do DF-Score na seção 2.2.** O texto trata "D-Score" e "F-Score" como dois modelos.
DF-Score é uma designação única — o *Dechow F-Score*.

**A.4 Referências citadas no corpo e ausentes na lista.** Cressey (1953), base do triângulo da
fraude, aparece no texto e não consta das referências. Piotroski, origem do PF-Score mencionado na
introdução, também não consta.

**A.5 Referências listadas e nunca citadas.** Jensen e Meckling (1976) e Lundberg e Lee (2017)
constam da lista sem aparecer no corpo. Lundberg e Lee é a referência do SHAP, que o texto não
menciona — vale incorporar interpretabilidade à metodologia (o pipeline já produz decomposição de
erro por atributo, que cumpre essa função) ou retirar a referência.

**A.6 Descrição de Hanifah et al. (2024) não corresponde à obra referenciada.** O corpo do texto
descreve um estudo sobre a teoria do pentágono da fraude em empresas listadas na bolsa da
Indonésia, com regressão múltipla. A referência listada é *"Analysis of Factors that Affect the
Effectiveness of Fraud Prevention Proxied by Professionalism and Internal Audit Experience and
Corporate Accountability"* (Khazanah Sosial), cujo título trata de outro objeto. Conferir se houve
troca de referência.

**A.7 Oscilação do escopo.** Vários trechos alternam entre "segmento S3" e "segmentos S2 e S3" —
por exemplo, o objetivo específico OE2 menciona apenas S3, e o delineamento (1.4) menciona apenas
S3, enquanto o objetivo geral abrange os dois. Uniformizar.

**A.8 Recorte temporal.** O texto afirma "período de 5 anos (2019-2024)" no resumo e "24
trimestres" na metodologia. De 2019 a 2024 são **seis** anos e 24 trimestres; a contagem de
trimestres está correta, a de anos não.

---

## Apêndice B — Referências utilizadas na construção do pipeline

BENEISH, Messod D. The detection of earnings manipulation. *Financial Analysts Journal*, v. 55,
n. 5, p. 24-36, 1999.

BENFORD, Frank. The law of anomalous numbers. *Proceedings of the American Philosophical Society*,
v. 78, n. 4, p. 551-572, 1938.

BENYASRISAWAT, Prawat; OUNLERT, Nadharatch. Fraud risk and audit opinions across countries:
complementing accounting-based fraud risk with machine learning methods. *Journal of Risk and
Financial Management*, v. 19, n. 1, p. 26, 2026.

BRASIL. Banco Central do Brasil. **Resolução CMN nº 2.682, de 21 de dezembro de 1999**. Dispõe
sobre critérios de classificação das operações de crédito e regras para constituição de provisão
para créditos de liquidação duvidosa.

BRASIL. Banco Central do Brasil. **Resolução CMN nº 4.553, de 30 de janeiro de 2017**. Estabelece
a segmentação do conjunto das instituições financeiras.

CHEN, Tianqi; GUESTRIN, Carlos. XGBoost: a scalable tree boosting system. In: *Proceedings of the
22nd ACM SIGKDD*. New York: ACM, 2016. p. 785-794.

DECHOW, P. M.; GE, W.; LARSON, C. R.; SLOAN, R. G. Predicting material accounting misstatements.
*Contemporary Accounting Research*, v. 28, n. 1, p. 17-82, 2011.

DYCK, Alexander; MORSE, Adair; ZINGALES, Luigi. How pervasive is corporate fraud? *Review of
Accounting Studies*, v. 28, 2020.

HILL, Theodore P. A statistical derivation of the significant-digit law. *Statistical Science*,
v. 10, n. 4, p. 354-363, 1995.

KE, G. et al. LightGBM: a highly efficient gradient boosting decision tree. *Advances in Neural
Information Processing Systems*, v. 30, p. 3146-3154, 2017.

LUNDBERG, Scott M.; LEE, Su-In. A unified approach to interpreting model predictions. *Advances in
Neural Information Processing Systems*, v. 30, p. 4765-4774, 2017.

NIGRINI, Mark J. *Benford's law: applications for forensic accounting, auditing, and fraud
detection*. Hoboken: Wiley, 2012.

PIOTROSKI, Joseph D. Value investing: the use of historical financial statement information to
separate winners from losers. *Journal of Accounting Research*, v. 38, p. 1-41, 2000.

SUNDARARAJAN, Mukund; TALY, Ankur; YAN, Qiqi. Axiomatic attribution for deep networks. In:
*Proceedings of the 34th International Conference on Machine Learning*, 2017. p. 3319-3328.
