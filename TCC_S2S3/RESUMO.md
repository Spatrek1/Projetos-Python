# Resumo da situação

> Documento de orientação: onde o projeto está, o que roda hoje e o que fazer a seguir.
> Para o projeto em profundidade, ver `docs/SINTESE_DO_PROJETO.md`.
> Para as decisões e por que foram tomadas, `HISTORICO.md`.

---

## 1. O que é este projeto

Detecção de **atipicidade contábil** em instituições financeiras dos segmentos S2 e S3, a partir
dos dados públicos do IF.data/COSIF do Banco Central, como apoio ao TCC *Auditorias em
instituições financeiras dos segmentos S2 e S3* (UFF).

**O que o código mede:** distância entre o comportamento de uma instituição e o padrão dos seus
pares e do seu próprio histórico.

**O que ele não mede:** fraude. Fraude é qualificação jurídica — exige intenção comprovada,
contraditório e decisão de autoridade competente. Escore alto é hipótese para direcionar
procedimento de auditoria, nunca achado.

Essa distinção não é formalidade. É ela que torna o trabalho defensável, e deve aparecer no texto
toda vez que um resultado for apresentado.

---

## 2. O problema central, e como foi resolvido

**Não existe rótulo de fraude.** Não há lista pública dizendo "este banco fraudou neste
trimestre". Sem rótulo não se treina um classificador — ele separaria o quê de quê?

A saída foi inverter a pergunta. Em vez de *"isto é fraude?"*, o modelo responde *"isto se parece
com o comportamento normal do setor?"*. Um **autoencoder** aprende a reconstruir observações de
período normal; quando erra muito ao reconstruir uma observação, é porque ela não se parece com o
que viu. Isso é anomalia.

> **Correção registrada.** Chegou-se a afirmar que o gargalo de compressão é o mecanismo que faz o
> autoencoder detectar anomalia. Os experimentos mostraram que não: a discriminação sobrevive sem
> compressão. O que faz funcionar é ele **só ver dados normais durante o treino**.

---

## 3. Os dados

| | |
|---|---|
| Fonte | IF.data / COSIF — Banco Central do Brasil |
| Recorte | 03/2019 a 12/2024 — 24 trimestres |
| Relatórios | 6 por trimestre: resumo, ativo, passivo, DRE, info de capital, segmentação |
| Arquivos | **144** (24 × 6) |
| Unidade | Conglomerado prudencial |
| Amostra | 1.347 observações, 72 instituições (9 S2, 66 S3) |
| Conceitos | 52 conceitos contábeis → 21 indicadores |

O enquadramento S2/S3 vem da coluna `SR` dos próprios relatórios, não de suposição.

> **Regra inviolável do projeto:** nenhum número é criado, imputado ou alterado. Conta ausente
> permanece ausente e aparece em `dados/tratados/pontos_de_correcao.csv`.

---

## 4. Decisões metodológicas que sustentam o trabalho

**Partição temporal, nunca aleatória.** São dados em painel: a mesma instituição aparece 24 vezes.
Sortear linhas colocaria o futuro de um banco no treino e seu passado no teste. Treino até 2022,
validação 2023, teste 2024.

**Guarda de circularidade.** O artigo de referência treina o modelo sobre componentes algébricos do
próprio rótulo. Replicamos e medimos o efeito: **AUC 0,97 com circularidade contra 0,60 sem ela.**
O módulo `vazamento.py` impede a contaminação e reporta os dois números — é dos resultados mais
fortes do trabalho.

**Classificação de evidência.** Cada indicador é marcado `LIT` (direto da literatura), `ADAP`
(adaptado de Beneish, Dechow, Piotroski ao balanço bancário) ou `PROP` (proposto aqui). Dos 21:
1 LIT, 9 ADAP, 11 PROP. A banca vai perguntar a origem de cada um.

**Piso de Basileia diferenciado.** 10,5 p.p. no regime geral; faixa de 13 a 18 para cooperativas,
com marcador de zona de incerteza onde a faixa não permite conclusão.

---

## 5. Os seis testes analíticos

Um procedimento substantivo por parâmetro contábil obrigatório. **Não dependem de treino, partição,
semente nem convergência** — qualquer terceiro reproduz a partir da base.

| | Parâmetro | Hipótese testada |
|---|---|---|
| **T1** | `provisao_pcld` | A provisão acompanha a exposição a risco de crédito |
| **T2** | `carteira_credito` | O crescimento é compatível com pares, capital e provisão |
| **T3** | `ativo_total` | A composição não migra para contas de mensuração discricionária |
| **T4** | `patrimonio_liquido` | A alavancagem e a folga de capital são compatíveis com os pares |
| **T5** | `resultado_intermediacao` | A margem é compatível com a carteira e com os pares |
| **T6** | `lucro_liquido` | O lucro é sustentado por operação recorrente |

Detalhamento, resultados e limitações em `docs/TESTES_ANALITICOS.md`.

### O achado que mais serve à defesa — e é negativo

Aplicado sem ressalva, **T1 sinalizava quase só bancos de atacado e de investimento** (Citibank,
Morgan Stanley, Goldman Sachs, JP Morgan, Deutsche). Provisionar pouco é o **modelo de negócio**
dessas instituições, não anomalia contábil.

A causa é estrutural: a **Res. CMN 4.553/2017 segmenta por porte e relevância sistêmica, não por
natureza da carteira**. Banco de atacado e cooperativa de varejo dividem o mesmo grupo de
comparação. O código TCB tampouco separa — Citibank, Deutsche e os bancos de varejo são todos `b1`.

A correção usa grandeza da própria base (`peso_carteira`): mediana de crédito/ativo de **4,9%** no
atacado contra **36,3%** nas demais instituições. Abaixo de 10% o crédito é imaterial e T1/T2 não
se aplicam.

> **Isto é resultado publicável, não defeito a esconder:** evidência empírica de que a segmentação
> regulatória é critério insuficiente de comparabilidade para análise contábil.

---

## 6. Situação atual dos dados

**Os 144 CSVs da base bruta foram perdidos** — na máquina local e no ambiente remoto. A base estava
em `.gitignore` sob o argumento de ser reproduzível a partir da fonte; o argumento é correto no
papel e saiu caro.

**O painel tratado, porém, sobreviveu** (entregue no pacote `TESTES-ANALITICOS`). Com ele:

| | Etapa | Roda? |
|---|---|---|
| 7 | Painel e partição temporal | sim |
| 8 | Auditoria de vazamento | sim |
| 9 | Autoencoder | sim |
| 10 | Rede sequencial (GRU) | sim |
| 11 | Comparação com métodos simples | sim |
| 12 | Interpretação | sim |
| 13 | Lei de Newcomb–Benford | **não** |
| 13.2 | Os seis testes analíticos | sim |
| 15 | XGBoost e LightGBM | sim |

**Benford é a única perda real.** Ela opera sobre os primeiros dígitos dos *valores contábeis
brutos*, e o painel disponível é de indicadores — razões, não valores. Exigiria
`painel_conceitos_S2S3.csv`. Era a triangulação independente da rede; os seis testes cumprem papel
parecido, mas não a substituem.

Sem a base bruta também não é possível: recalcular o painel, acrescentar indicador novo, ou
conferir um número contra o relatório de origem.

Para saber exatamente o que roda com o que existe na sua pasta:

```bash
python testes/conferir_painel_tratado.py
```

---

## 7. Os comandos do projeto

Rode sempre pelo **terminal** (`Ctrl + '` no VS Code), nunca pelo `F5` — o depurador transforma
saída normal de programa em "exceção" e confunde.

```bash
python testes/conferir_painel_tratado.py    # o que roda com o que você tem
python testes/validar_extracao_manual.py    # confere a base bruta (grade relatório × trimestre)
python processar_base.py                    # produz o painel tratado
python testes/test_pipeline.py              # confere o código — 21 testes
```

Códigos de saída de `processar_base.py`: **2** = base não encontrada, **3** = base ilegível.
Nenhum dos dois é erro de programa.

---

## 8. O que falta fazer

### No código

1. **Resgatar o painel tratado** da pasta `TESTES-ANALITICOS` para `dados/tratados/` e rodar a
   conferência.
2. **Rodar o notebook da seção 7 em diante** sobre o painel real — primeira execução de verdade
   das redes.
3. **Refazer a base bruta**, sem pressa, seguindo `dados/ifdata_bruto/CHECKLIST_DOWNLOADS.md`.
   São **144** arquivos, não 96 — o checklist antigo estava errado e omitia `passivo` e
   `info de cap`, que sustentam T4 e a concentração de captação.
4. **Versionar a base** quando ela voltar, para não repetir a perda.
5. **Decidir `PESO_MINIMO_CARTEIRA`** (hoje 10%) em `src/fraude_s2s3/testes_analiticos.py`, rodar
   `sensibilidade()` variando esse corte, e registrar no texto que T1 e T2 são condicionais a ele.
6. **Preencher `dados/externos/eventos_publicos.csv`** com liquidações, RAETs e intervenções do
   Bacen — sem isso a seção 14 não tem contra o que validar.
7. **Três inspeções** apontadas em `pontos_de_correcao.csv`: composição por nível de risco das
   instituições com provisão zero; cooperativas na zona de incerteza do piso de Basileia;
   observações com folga de Basileia negativa.

### No texto do TCC

Detalhamento no **Apêndice A** de `HISTORICO.md`. Os dois primeiros são os que a banca levanta
antes de qualquer outro:

1. **O título fala em LLMs**, mas o método é rede neural e gradient boosting. São coisas
   diferentes, e a divergência é visível na capa.
2. **A seção 2.4 atribui "M-Score e F-Score"** ao artigo de referência, que usa **DF-Score e
   PF-Score**.
3. A descrição de Hanifah et al. (2024) não corresponde ao trabalho citado.
4. Cressey e Piotroski são citados no texto e faltam nas referências.

---

## 9. Por onde ler

| Arquivo | Conteúdo |
|---|---|
| `README.md` | o projeto em uma página |
| `docs/SINTESE_DO_PROJETO.md` | o projeto inteiro, com as decisões |
| `docs/TESTES_ANALITICOS.md` | os seis testes, resultados e limitações |
| `docs/FLUXOGRAMA.md` | os diagramas do pipeline |
| `docs/GUIA_EXTRACAO_MANUAL.md` | como baixar os 144 arquivos |
| `docs/DOCUMENTACAO_MODULOS.md` | cada módulo do código |
| `HISTORICO.md` | o que foi decidido e por quê — **Apêndice A: correções no texto** |
