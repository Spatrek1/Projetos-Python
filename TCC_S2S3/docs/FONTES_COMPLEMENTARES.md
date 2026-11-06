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

### 1.5 Como navegar cada fonte

> As URLs dos portais `gov.br` mudam com frequência, e **não foi possível
> conferi-las ao escrever esta seção** — a política de rede do ambiente em que o
> código foi desenvolvido bloqueia `bcb.gov.br`, `cvm.gov.br` e `in.gov.br`. Por
> isso o que segue descreve **caminhos de navegação e termos de busca**, não
> endereços. Confira cada link antes de citar, e registre a data de acesso.

**Banco Central — regimes especiais.** No portal do BCB, procure a área de
*Estabilidade financeira* e, dentro dela, *Regimes especiais* ou *Liquidações*.
O BCB mantém relação das instituições em regime especial, com a data do ato e o
tipo de regime, incluindo encerrados. É o ponto de partida: dá a lista; o DOU dá
o documento.

**Diário Oficial da União — a fonte primária.** O portal da Imprensa Nacional
tem busca por período e por termo. Procure pelo **nome da instituição** e, em
paralelo, por expressões do ato: *"liquidação extrajudicial"*, *"regime de
administração especial temporária"*, *"intervenção"*, *"cancelamento da
autorização para funcionamento"*. O ato traz número, data, autoridade e
fundamento legal — é isso que se cita, não a notícia sobre ele.

**Sancionadores do BCB.** Procure por *processo administrativo sancionador* no
portal do BCB. A Lei 13.506/2017 rege o rito atual e mudou a forma de
publicação, então o formato difere entre o começo e o fim do seu recorte — vale
registrar isso no TCC.

**CVM.** Para instituições de capital aberto: o portal de dados abertos da CVM
publica fatos relevantes e processos sancionadores em arquivos por ano,
baixáveis e filtráveis — mais confiável que a busca da página.

### 1.6 CRSFN — a fonte que costuma passar despercebida

O **Conselho de Recursos do Sistema Financeiro Nacional**, o "Conselhinho",
julga os recursos contra decisões sancionadoras do BCB e da CVM. Está vinculado
ao Ministério da Fazenda, e seus **acórdãos são públicos**.

Por que importa mais do que parece: o acórdão costuma **descrever a infração**,
e isso permite separar o que interessa ao estudo — divergência em informação
contábil, classificação de risco de crédito, provisionamento — do que não
interessa, como falha cadastral. É a melhor fonte para montar um rótulo
*específico de manipulação contábil*, em vez de um rótulo genérico de "sanção".

A contrapartida: só chega ao CRSFN o que foi recorrido, e o julgamento é anos
posterior ao fato. Serve para **qualificar** eventos, não para datá-los.

### 1.7 FGC — sinal indireto

O Fundo Garantidor de Créditos divulga os pagamentos de garantia, que
acompanham liquidações. Não é fonte primária do evento, mas serve de
**conferência cruzada**: pagamento de garantia sem ato correspondente na sua
planilha significa que você perdeu um caso.

### 1.8 O problema da defasagem de divulgação

**Este é o ponto que mais ameaça a conclusão, e o mais fácil de não enxergar.**

O pipeline considera sinalizado o escore nos `janela_antecedencia = 4`
trimestres **anteriores** ao evento. Mas o IF.data não é publicado no
fechamento do trimestre: há defasagem de alguns meses entre a data-base e a
divulgação.

Consequência: para um evento em junho, o trimestre imediatamente anterior
(março) pode ter sido divulgado praticamente junto com o evento. Dizer que o
modelo "antecipou" usando aquele trimestre é frágil — naquele momento o dado
ainda não era público.

Duas saídas, e **a escolha precisa estar no texto**:

1. **Descartar o trimestre mais próximo** e contar a antecedência a partir de
   t−2. Conservador, e o que se defende melhor na banca.
2. **Manter os quatro trimestres**, mas reportar separadamente quantos acertos
   dependem do trimestre mais próximo.

Em qualquer caso, levante a data de divulgação efetiva de cada data-base e
registre-a. Não é detalhe: é a diferença entre "o modelo antecipou" e "o modelo
viu o que já estava acontecendo".

### 1.9 Casar o ato com o `cod_inst`

Obstáculo prático que aparece na hora de preencher a planilha: o ato do BCB
nomeia a **instituição** e traz o **CNPJ**; o seu painel é de **conglomerado
prudencial**, cujo código não é o CNPJ.

Uma instituição liquidada pode ser parte de um conglomerado que continua
existindo, ou ser o próprio conglomerado. São situações diferentes e produzem
rótulos diferentes. Use o relatório de **resumo** do IF.data, que traz a
identificação, para fazer a correspondência, e **registre no TCC o critério
adotado** quando o ato atinge parte de um conglomerado.

### 1.10 Quantos eventos esperar — e o que fazer se forem poucos

Sua amostra tem 72 instituições em 24 trimestres. Regimes especiais em S2/S3
nesse recorte são **raros**: é inteiramente possível terminar com meia dúzia de
eventos, ou com nenhum.

Isso não invalida o trabalho, mas **muda o que ele pode afirmar**, e é melhor
decidir agora do que ao escrever a conclusão:

| Eventos encontrados | O que o TCC pode afirmar |
|---|---|
| 0 | Nada sobre antecipação. O trabalho se sustenta na atipicidade e nos seis testes, e a ausência de eventos no recorte é em si um resultado a relatar. |
| 1 a 5 | Análise **de casos**, nominal e descritiva. Nenhuma métrica agregada — AUC sobre 3 eventos não significa nada. |
| 6 ou mais | Métricas agregadas, sempre com o número de eventos ao lado e intervalo de confiança. |

Decida o critério **antes** de olhar os resultados e registre a decisão. Escolher
a métrica depois de ver qual favorece é o erro que a banca identifica mais
rápido.

### 1.11 Um sinal que vem do próprio painel

Independente de qualquer fonte externa: **instituições que desaparecem do painel**
entre um trimestre e outro. Isso é observável nos seus próprios dados e não
custa nada levantar.

A ressalva é séria: desaparecer pode significar liquidação, mas também fusão,
incorporação, mudança de segmento ou reorganização societária — e as duas
primeiras são comuns no período. **Não use como rótulo sozinho.** Use como
*lista de candidatos* a investigar nas fontes acima: é um jeito eficiente de
descobrir quais instituições merecem busca no DOU, em vez de procurar as 72.

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
