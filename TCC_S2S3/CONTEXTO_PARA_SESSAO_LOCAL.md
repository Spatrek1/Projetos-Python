# Contexto para continuidade em sessão local

Documento de transferência. Uma sessão nova do Claude Code não tem acesso ao
histórico da conversa anterior — este arquivo reconstrói o estado do trabalho.

**Como usar:** abra `C:\Documentos\Projetos-Python` no Claude Code e diga:
*"Leia TCC_S2S3/CONTEXTO_PARA_SESSAO_LOCAL.md e continue de onde parou."*

---

## 1. O que é o projeto

Apoio ao TCC *Auditorias em instituições financeiras dos segmentos S2 e S3*
(Fernando Ulerich Fonseca, Ciências Contábeis, UFF).

Pipeline de rede neural sobre dados públicos do **IF.data/COSIF** (Banco
Central do Brasil), período 2019–2024, para identificar **atipicidade
contábil** em instituições dos segmentos S2 e S3.

Referência metodológica principal: Benyasrisawat e Ounlert (2026), *Fraud Risk
and Audit Opinions Across Countries*, J. Risk Financial Manag., v. 19, n. 1,
p. 26.

## 2. A premissa que atravessa tudo

**O código não detecta fraude.** Mede atipicidade: distância entre o
comportamento de uma instituição e o padrão dos pares e do próprio histórico.
Fraude é qualificação jurídica — exige intenção comprovada, contraditório e
decisão de autoridade competente.

Isso não é formalidade de redação. Dyck, Morse e Zingales (2020) estimam que
apenas cerca de um terço das fraudes corporativas é detectado; o conjunto de
instituições sem evento público conhecido mistura instituições íntegras e
irregularidades nunca vindas a público. Nenhum modelo treinado nesses dados
separa as duas coisas.

Ao redigir qualquer saída, preservar essa distinção.

## 3. Três decisões de projeto que não devem ser revertidas sem discussão

### 3.1 Autoencoder em vez de classificador

Não existe rótulo público de fraude bancária no Brasil. Um classificador
exigiria inventar o alvo, e a métrica passaria a medir concordância com a
invenção. O autoencoder dispensa rótulo: aprende a região do espaço onde vivem
os dados normais e pontua pelo erro de reconstrução.

Verificação empírica feita (dados sintéticos, apenas para entender o
mecanismo): o poder de discriminação vem principalmente de a rede **só ver
dados normais no treino**, não do gargalo. Com amostra pequena (n=40) a rede
memoriza — erro de treino 0,00026 contra 0,05075 em normais inéditos — e o
ganho aparente desaparece quando medido fora da amostra.

### 3.2 Guarda de circularidade (`src/fraude_s2s3/vazamento.py`)

No artigo de referência, o XGBoost prevê o DF-Score usando como atributos os
**próprios componentes que definem o DF-Score** (soma de RSST_ACC, CH_REC,
CH_INV, SOFT_ASSETS, CH_CS, CH_CM, CH_ROA, CH_FCF — Tabela 3). As métricas
reportadas na Tabela 5 (acurácia 0,995, AUC-ROC 0,999) são compatíveis com um
modelo que reaprende uma identidade aritmética.

Isso **não invalida o artigo** — o objeto dele é a relação entre risco de
fraude e opinião de auditoria, estimada depois por IV-2SLS. Invalida a leitura
de que "AUC 0,999 demonstra capacidade de detecção".

O notebook (seção 15) roda as duas versões, com e sem os componentes, e reporta
lado a lado. Em ensaio sobre painel sintético, a diferença foi AUC 0,97 → 0,60.
Essa lacuna é um resultado do TCC.

### 3.3 Indicadores adaptados ao balanço bancário

Beneish, Dechow e Piotroski foram calibrados em empresas **não financeiras**:
não há estoque, margem bruta nem vendas em banco. A adaptação é por analogia
funcional (ver `src/fraude_s2s3/indicadores.py`), mais indicadores prudenciais
propostos a partir da Res. CMN 2.682/1999 e de Basileia — cobertura de
provisão, descasamento provisão × inadimplência, peso do crédito tributário,
folga de Basileia.

Cada indicador declara sua classe de evidência: `LIT` (literatura), `ADAP`
(adaptado), `PROP` (proposto pelo autor, sem validação prévia). Manter essa
distinção visível no texto do TCC.

## 4. Estado atual

**Pronto e verificado:** 13 módulos em `src/fraude_s2s3/`, notebook de 16
seções (51 células), 16 testes passando, execução ponta a ponta sem erro.

**Não verificado:** nada rodou contra dados reais. O ambiente anterior tinha
`bcb.gov.br` bloqueado por política de rede. **Numa sessão local isso
provavelmente não existe** — é a primeira coisa a testar.

## 5. Próximos passos, em ordem

1. `python testes\diagnostico_rede.py` — confirma acesso ao IF.data.
2. Notebook, seção 2 — descobre o esquema real do serviço OData e lista os
   relatórios publicados. **Não presumir nomes de recurso ou coluna.**
3. Preencher `RELATORIOS` e `TIPOS_INSTITUICAO` na seção 2.1 com o que a
   seção 2 revelar.
4. Ajustar `src/fraude_s2s3/mapeamento.py` aos rótulos reais dos relatórios.
5. Rodar o pipeline e ler a seção 16 (pontos de correção).

## 6. Pendências que dependem do pesquisador

Arquivos que o pipeline procura em `dados/externos/` (ver `LEIA-ME.md` lá):

| Arquivo | Sem ele |
|---|---|
| `segmentacao_oficial.csv` | Pipeline reconstrói S2/S3 pela regra Exposição/PIB e emite pendência **bloqueante** |
| `pib_trimestral.csv` | Alternativa ao acima |
| `eventos_publicos.csv` | O TCC só afirma "atipicidade", sem ponte com problema real |

Decisão pendente de orientação: **conglomerado prudencial ou instituição
individual?** Muda quem é S2 e quem é S3.

## 7. Observações sobre o texto do projeto de pesquisa

Detalhadas no Apêndice A do `HISTORICO.md`. As três principais:

- o título anuncia **LLMs**, mas o método é XGBoost/LightGBM (que não são LLMs);
- a seção 2.4 atribui ao artigo de referência a combinação de "M-Score e
  F-Score"; ele usa **DF-Score e PF-Score**;
- a descrição de Hanifah et al. (2024) no corpo não corresponde ao título da
  obra referenciada — conferir se houve troca de referência.

Faltam Cressey e Piotroski na lista de referências; sobram Jensen/Meckling e
Lundberg/Lee (listados, nunca citados no corpo).

## 8. Convenções do código

- Comentários, docstrings e mensagens em **português**.
- Nenhuma limitação encontrada durante a execução deve virar `NaN` silencioso:
  registrar em `diagnostico.registrar()` com área responsável e ação pedida.
- Indicadores sem insumo são **omitidos e reportados**, nunca preenchidos com zero.
- Partição temporal, nunca aleatória (painel contábil é persistente dentro da
  instituição; divisão aleatória vaza o futuro).
- Normalização ajustada **apenas no treino**.

## 9. Leitura recomendada, nesta ordem

1. `README.md` — visão geral e início rápido
2. `HISTORICO.md` — decisões metodológicas e justificativas
3. `notebooks/00_pipeline_s2_s3.ipynb` — o pipeline
4. `src/fraude_s2s3/vazamento.py` — a contribuição metodológica central
5. `dados/externos/LEIA-ME.md` — o que falta fornecer
