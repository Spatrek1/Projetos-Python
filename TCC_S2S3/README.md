# Detecção de atipicidade contábil em instituições financeiras S2 e S3

Pipeline de rede neural sobre dados públicos do **IF.data/COSIF** (Banco Central do Brasil), como
apoio ao TCC *Auditorias em instituições financeiras dos segmentos S2 e S3* — Universidade Federal
Fluminense.

> **O que este código mede.** Atipicidade contábil: distância entre o comportamento de uma
> instituição e o padrão dos seus pares e do seu próprio histórico.
>
> **O que ele não mede.** Fraude. Fraude é qualificação jurídica — exige intenção comprovada,
> contraditório e decisão de autoridade competente. Um escore alto é hipótese para direcionar
> procedimento de auditoria, não achado.

---

## Início rápido

```bash
pip install -r requirements.txt
python testes/test_pipeline.py              # verificação: 21 testes
python testes/conferir_painel_tratado.py    # o que roda com os dados que você tem
```

Com a base bruta em `dados/ifdata_bruto/`, um comando produz tudo:

```bash
python processar_base.py
jupyter lab notebooks/00_pipeline_s2_s3.ipynb
```

A **seção 2 do notebook decide a rota sozinha**, nesta ordem: painel já tratado, base bruta local,
API, fumaça. A exportação manual é a rota desta pesquisa; o serviço OData é a última tentativa, não
a primeira, e sua indisponibilidade não interrompe nada.

Para verificar a execução sem rede, altere `USAR_DADOS_REAIS = False`. Isso usa um painel
**artificial** — nenhum número desse modo pode aparecer no TCC.

---

## Antes de rodar com dados reais

Três arquivos precisam ser fornecidos em `dados/externos/` (instruções em `dados/externos/LEIA-ME.md`):

| Arquivo | Necessidade | Sem ele |
|---|---|---|
| `segmentacao_oficial.csv` | Enquadramento oficial S1–S5 por data-base | Pipeline reconstrói pela regra Exposição/PIB e emite **pendência bloqueante** |
| `pib_trimestral.csv` | Alternativa ao acima | Sem nenhum dos dois, não há como delimitar S2/S3 |
| `eventos_publicos.csv` | Eventos datados e verificáveis | O TCC só pode afirmar "atipicidade", sem ponte com problema real |

---

## Estrutura

```
src/fraude_s2s3/
├── config.py         Todos os parâmetros metodológicos, isolados do código
├── ifdata.py         Coleta com descoberta de esquema em tempo de execução
├── segmentacao.py    S2/S3 — lista oficial ou regra da Res. CMN 4.553/2017
├── mapeamento.py     Rótulos do IF.data → conceitos contábeis, com diagnóstico
├── indicadores.py    Beneish/Dechow/Piotroski adaptados ao balanço bancário
├── painel.py         Winsorização, z-score por pares, partição cronológica
├── vazamento.py      Guarda de circularidade entre atributos e rótulo
├── redes.py          Autoencoder denoising, GRU sequencial, rede híbrida
├── baselines.py      PCA, Mahalanobis robusto, Isolation Forest, XGBoost, LightGBM
├── avaliacao.py      Validação por eventos, Precision@k, estabilidade
├── benford.py        Triangulação independente por Newcomb–Benford
├── interpretacao.py  Decomposição exata do erro; Integrated Gradients
└── diagnostico.py    Registro e consolidação dos pontos de correção

notebooks/00_pipeline_s2_s3.ipynb    Pipeline completo, 16 seções
HISTORICO.md                         Decisões metodológicas e justificativas
testes/test_pipeline.py              16 testes do pipeline
```

---

## Três decisões que diferenciam este pipeline de uma replicação direta

**1. Autoencoder em vez de classificador.** Não existe rótulo público de fraude bancária no Brasil.
Um classificador exigiria inventar o alvo — e a métrica passaria a medir concordância com a
invenção. O autoencoder dispensa rótulo: aprende a normalidade do conjunto e pontua pelo erro de
reconstrução.

**2. Guarda de circularidade.** No artigo de referência, o XGBoost prevê o DF-Score a partir dos
próprios componentes do DF-Score, que é definido como a soma deles — daí o AUC-ROC de 0,999. O
pipeline detecta e bloqueia esse padrão, e reporta as duas versões (com e sem os componentes)
lado a lado. A diferença entre elas é resultado do trabalho. Ver `HISTORICO.md`, seção 3.

**3. Indicadores prudenciais bancários.** Beneish, Dechow e Piotroski foram calibrados em empresas
não financeiras: não há estoque, margem bruta nem vendas em banco. Além da adaptação por analogia
funcional, foram propostos indicadores do arcabouço prudencial — cobertura de provisão,
descasamento provisão × inadimplência, peso do crédito tributário, folga de Basileia. O
subprovisionamento é o canal mais direto de inflar resultado em instituição financeira e não é
capturado por nenhum modelo original.

---

## Pontos de correção

O pipeline registra cada limitação **no momento em que ela aparece**, com área responsável e ação
pedida, e consolida tudo na seção 16 do notebook. Itens `BLOQUEIA RESULTADO` significam que os
escores daquela execução não devem ser reportados no TCC enquanto não forem resolvidos.

Indicadores sem insumo são omitidos e reportados — nunca preenchidos com zero.

---

## Saídas geradas

Em `resultados/`: `escores_atipicidade.csv`, `decomposicao_erro.csv`, `ranking_atributos.csv`,
`quadro_operacionalizacao.csv` (anexo do TCC) e `pontos_de_correcao.csv`.

---

## Reprodutibilidade

O IF.data admite republicação de períodos anteriores quando a instituição reapresenta documento.
Coletas em datas diferentes podem produzir painéis diferentes — **cite no TCC a data de coleta**,
que o cliente grava no atributo `coletado_em` de cada resposta.
