# Fontes oficiais para cruzamento com o IF.data

Fontes públicas e oficiais que complementam o IF.data, organizadas pelo **papel
que cumprem no desenho da pesquisa** — não por órgão emissor.

> **Nota.** Este documento foi escrito sem acesso à rede aos sites citados
> (o ambiente de desenvolvimento tem `bcb.gov.br` bloqueado). Os nomes das
> bases e o que cada uma entrega estão descritos com precisão; **navegue a
> partir do portal oficial de cada órgão** em vez de confiar em endereços
> transcritos, e registre no TCC a URL e a data de acesso que você usou.

---

## Sumário por finalidade

| Finalidade | Fonte | Prioridade |
|---|---|---|
| Rótulo de eventos (validação externa) | BCB — atos de liquidação, RAET, intervenção | **Alta** |
| Rótulo de eventos | BCB — processos administrativos sancionadores | Alta |
| Rótulo de eventos | CVM — processos sancionadores e fatos relevantes | Média |
| Validação contábil cruzada | CVM — DFP/ITR de bancos de capital aberto | **Alta** |
| Viés de sobrevivência | BCB — cadastro de instituições (Unicad) | **Alta** |
| Identificação e estrutura societária | Receita Federal — dados abertos de CNPJ | Média |
| Variáveis de contexto | BCB — SGS (séries temporais) | Média |
| Variáveis de contexto | IBGE — Contas Nacionais Trimestrais | Baixa* |
| Granularidade adicional | BCB — ESTBAN, SCR | Baixa |

\* Baixa porque a segmentação oficial vem na coluna `SR` do IF.data; a série de
PIB deixou de ser necessária para delimitar S2/S3.

---

## 1. Eventos públicos — o que dá alcance à conclusão

Esta é a lacuna mais importante do desenho atual. Sem eventos verificáveis, o
trabalho só pode afirmar *"identifiquei instituições contabilmente atípicas"*.
Com eles, passa a afirmar *"o escore subiu N trimestres antes de eventos que
efetivamente ocorreram"* — conclusão de outra ordem.

### 1.1 Banco Central — regimes especiais

O BCB publica os atos de **liquidação extrajudicial**, **regime de
administração especial temporária (RAET)** e **intervenção**, com data.

Onde procurar: portal do BCB, seção de estabilidade financeira / regimes
especiais; e a publicação correspondente no **Diário Oficial da União**
(Imprensa Nacional), que traz o ato na íntegra e é a fonte primária citável.

O que extrair para `dados/externos/eventos_publicos.csv`:

```csv
cod_inst,anomes_evento,tipo_evento,fonte
1000080329,202312,LIQUIDACAO_EXTRAJUDICIAL,<URL do ato no DOU>
```

**Atenção à data.** Use a data do **ato**, não a data em que os fatos
supostamente ocorreram. O pipeline exclui os trimestres posteriores ao evento
justamente porque o balanço pós-intervenção reflete a intervenção.

### 1.2 Banco Central — processos administrativos sancionadores

Decisões sancionadoras contra instituições e administradores. Mais numerosas
que os regimes especiais e, portanto, mais úteis estatisticamente — mas
cobrem infrações de natureza variada, nem todas ligadas a manipulação
contábil.

**Recomendação:** classifique por natureza da infração e reporte separadamente.
Misturar sanção por descumprimento cadastral com sanção por informação
contábil incorreta enfraquece o rótulo.

### 1.3 CVM — sancionadores e fatos relevantes

Aplicável apenas às instituições de capital aberto. Processos sancionadores,
termos de compromisso e fatos relevantes ficam no portal da CVM, com dados
abertos disponíveis.

### 1.4 O que **não** usar como rótulo

Notícia de imprensa sobre investigação em curso. Investigação não é evento
comprovado, e transformar suspeita noticiada em rótulo de treino é o tipo de
escolha que inviabiliza o trabalho na banca.

Se quiser incluí-las, use um `tipo_evento` distinto (ex.: `APURACAO_EM_CURSO`)
e reporte os resultados em separado, deixando explícito o estatuto diferente
dessas observações.

---

## 2. CVM — validação contábil cruzada

**A fonte que pode elevar o alcance do trabalho.**

Bancos de capital aberto depositam na CVM as demonstrações financeiras
padronizadas (**DFP**, anual) e as informações trimestrais (**ITR**). Esses
documentos trazem duas coisas que o IF.data não tem:

**a) Demonstrações auditadas completas**, incluindo demonstração dos fluxos de
caixa e notas explicativas. Isso permite:

- **conferir** se os saldos do IF.data batem com os publicados — validação
  direta da sua base;
- substituir o *proxy* de accrual bancário por accrual calculado com o fluxo
  de caixa operacional real (hoje o `accrual_bancario` é aproximação declarada,
  por ausência de DFC no IF.data).

**b) O parecer do auditor independente** — com ou sem ressalva, com ou sem
ênfase, com ou sem parágrafo de incerteza sobre continuidade operacional.

Esse segundo ponto merece atenção especial. **A opinião de auditoria é
exatamente a variável dependente de Benyasrisawat e Ounlert (2026)**, que o
seu projeto usa como referência. Com ela, você pode reproduzir o segundo
estágio do desenho deles — a relação entre risco de fraude e resposta do
auditor — para o subconjunto de bancos listados.

**Limitação a declarar:** poucos bancos S2/S3 têm capital aberto. Isso vira
uma **subamostra**, não a amostra principal. Reporte como análise
complementar, com o número de instituições explícito.

Onde procurar: Portal de Dados Abertos da CVM (documentos periódicos e
eventuais das companhias abertas).

---

## 3. Cadastro de instituições — o viés de sobrevivência

O pipeline exige mínimo de 8 trimestres por instituição e **registra pendência**
sobre isso, porque instituições que deixaram de operar no período são as de
maior interesse forense — e as mais propensas a ter histórico curto.

O cadastro de instituições autorizadas do BCB (**Unicad**, ou a relação de
instituições em funcionamento) permite distinguir os motivos da saída:

| Motivo da saída | Interpretação |
|---|---|
| Incorporação / fusão | Saída "normal"; a instituição continua dentro de outro grupo |
| Cancelamento voluntário | Saída sem indício |
| Liquidação / intervenção | **Evento de interesse** — vira linha no arquivo de eventos |

Sem essa distinção, o TCC não consegue afirmar se a exclusão foi neutra ou
enviesada. Com ela, a descrição da amostra fica defensável.

---

## 4. Receita Federal — dados abertos de CNPJ

Cadastro nacional de pessoas jurídicas, com situação cadastral, data de
alteração, quadro societário e vínculos entre empresas.

Uso possível: identificar mudanças de controle e reorganizações societárias
que expliquem quebras na série contábil — evitando que uma reestruturação seja
lida como anomalia.

**Cautela:** o cruzamento exige o CNPJ, e o IF.data identifica por código de
instituição. A ponte entre os dois identificadores precisa ser feita e
documentada; não presuma correspondência automática.

---

## 5. Séries temporais — variáveis de contexto

### 5.1 BCB — SGS (Sistema Gerenciador de Séries Temporais)

Séries macroeconômicas e do sistema financeiro: taxa Selic, inadimplência
agregada por modalidade, spread bancário, saldo de crédito.

Uso no desenho atual: o z-score por pares já controla o efeito de ciclo
econômico ao padronizar dentro de (segmento, trimestre). As séries do SGS
servem para **interpretar** um pico de atipicidade em determinado trimestre
— por exemplo, distinguir deterioração idiossincrática de movimento setorial.

### 5.2 IBGE — Contas Nacionais Trimestrais

PIB trimestral. Deixou de ser necessário para delimitar S2/S3, já que a
segmentação oficial vem na coluna `SR`. Continua útil se você quiser reportar
a razão Exposição/PIB como estatística descritiva.

### 5.3 BCB — Relatório de Estabilidade Financeira

Publicação semestral com a leitura do próprio supervisor sobre riscos do
sistema. Não é base de dados, é **fonte interpretativa**: útil para confrontar
os períodos em que o seu escore agregado subiu com o diagnóstico oficial da
época.

---

## 6. Granularidade adicional

**ESTBAN** — estatística bancária mensal por município: depósitos e operações
de crédito por agência. Permite detectar concentração geográfica anômala.

**SCR** — Sistema de Informações de Créditos: dados agregados de crédito por
modalidade e faixa de risco. Complementa a carteira por nível de risco.

Ambas ampliam o espaço de atributos, mas **aumentam a dimensionalidade sem
aumentar o número de instituições** — e com 48 instituições em S2/S3, mais
colunas pioram a razão parâmetros/observações da rede. Use com parcimônia, e
só se um indicador específico justificar.

---

## 7. Como registrar no TCC

Para cada fonte efetivamente usada, registre:

| Item | Por quê |
|---|---|
| Nome da base e órgão | Identificação |
| URL de acesso | Verificabilidade |
| **Data de extração** | Bases oficiais são revisadas |
| Recorte aplicado | Reprodutibilidade |
| Chave de ligação com o IF.data | O cruzamento precisa ser auditável |

A chave de ligação merece cuidado especial: IF.data identifica por **código de
instituição**; CVM por **código CVM**; Receita por **CNPJ**. Cada ponte é uma
decisão metodológica, e cada correspondência malfeita é um dado errado que
entra no painel sem aviso.

---

## 8. Ordem de prioridade sugerida

Se o tempo for limitado, esta é a ordem que mais agrega ao trabalho:

1. **Eventos do BCB** (liquidação, RAET, intervenção) — sem isso a seção 14 do
   notebook não roda, e a conclusão fica restrita a "atipicidade"
2. **Cadastro de instituições** — resolve o viés de sobrevivência na descrição
   da amostra
3. **CVM (DFP/ITR)** para os bancos listados — valida a base e abre a
   possibilidade de reproduzir o segundo estágio do artigo de referência
4. O restante, conforme necessidade
