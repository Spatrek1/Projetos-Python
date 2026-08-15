# Dados externos (fornecidos pelo pesquisador)

Três arquivos que o pipeline procura aqui. Nenhum é gerado automaticamente: todos dependem de
fonte que precisa ser conferida por você e citada no TCC.

---

## 1. `segmentacao_oficial.csv` — **prioridade máxima**

Enquadramento oficial das instituições nos segmentos S1–S5, por data-base.

```csv
cod_inst,anomes,segmento
12345678,201903,S3
12345678,201906,S3
```

**Por que importa mais que tudo.** O recorte amostral é a primeira coisa que a banca questiona. Sem
este arquivo, o pipeline reconstrói o enquadramento pela regra Exposição/PIB da Resolução CMN
4.553/2017 — e registra pendência **bloqueante**, porque reconstrução não é a classificação do
supervisor. A norma considera exposições fora do balanço e revisa o enquadramento em datas-base
próprias; a razão calculada sobre o ativo contábil é aproximação por baixo.

**Onde obter.** Banco Central do Brasil. Se não houver série histórica publicada para todo o
recorte, registre no TCC qual data-base foi usada e se o enquadramento foi mantido fixo.

---

## 2. `pib_trimestral.csv` — alternativa ao item 1

PIB acumulado em 12 meses, em reais correntes, por trimestre.

```csv
anomes,pib
201903,7100000000000
```

Só é usado quando `segmentacao_oficial.csv` não existe. **A escolha da série muda o denominador e,
portanto, muda quem entra em S2 e em S3** — registre no TCC a série exata (fonte, código, data de
extração). Séries candidatas: Contas Nacionais Trimestrais do IBGE; séries do SGS/BCB.

---

## 3. `eventos_publicos.csv` — define o alcance da conclusão

Ver instruções detalhadas em `eventos_publicos_MODELO.csv`.

Sem este arquivo, o TCC só pode afirmar *"identifiquei instituições contabilmente atípicas"*. Com
eventos verificáveis, pode afirmar *"o escore subiu N trimestres antes de eventos que efetivamente
ocorreram"* — que é uma conclusão de outra ordem.

**A distinção que não pode ser perdida:** investigação noticiada não é evento comprovado. Se
incluir casos sob apuração, use tipo de evento distinto e reporte em separado. Transformar suspeita
de imprensa em rótulo de treino é o erro que inviabiliza o trabalho na banca.

---

## Reprodutibilidade

Anote, para cada arquivo: fonte, data de extração e versão. O IF.data admite republicação de
períodos anteriores quando a instituição reapresenta documento — coletas em datas diferentes podem
produzir painéis diferentes, e o TCC precisa dizer qual foi a sua.
