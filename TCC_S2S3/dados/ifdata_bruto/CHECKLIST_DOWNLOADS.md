# Controle dos downloads do IF.data

Marque cada arquivo conforme baixar. Preencha a data no rodapé —
ela precisa constar no TCC (o IF.data republica períodos quando há
reapresentação de documento).

**Recorte escolhido:** ( ) conglomerado prudencial   ( ) instituição individual

> Escolha um e mantenha em TODOS os downloads. Misturar os dois
> duplica instituições e contamina a comparação entre segmentos.

| # | Trimestre | resumo | ativo | resultado | segmentacao |
|---|---|---|---|---|---|
| 01 | 03/2019 | [ ] | [ ] | [ ] | [ ] |
| 02 | 06/2019 | [ ] | [ ] | [ ] | [ ] |
| 03 | 09/2019 | [ ] | [ ] | [ ] | [ ] |
| 04 | 12/2019 | [ ] | [ ] | [ ] | [ ] |
| 05 | 03/2020 | [ ] | [ ] | [ ] | [ ] |
| 06 | 06/2020 | [ ] | [ ] | [ ] | [ ] |
| 07 | 09/2020 | [ ] | [ ] | [ ] | [ ] |
| 08 | 12/2020 | [ ] | [ ] | [ ] | [ ] |
| 09 | 03/2021 | [ ] | [ ] | [ ] | [ ] |
| 10 | 06/2021 | [ ] | [ ] | [ ] | [ ] |
| 11 | 09/2021 | [ ] | [ ] | [ ] | [ ] |
| 12 | 12/2021 | [ ] | [ ] | [ ] | [ ] |
| 13 | 03/2022 | [ ] | [ ] | [ ] | [ ] |
| 14 | 06/2022 | [ ] | [ ] | [ ] | [ ] |
| 15 | 09/2022 | [ ] | [ ] | [ ] | [ ] |
| 16 | 12/2022 | [ ] | [ ] | [ ] | [ ] |
| 17 | 03/2023 | [ ] | [ ] | [ ] | [ ] |
| 18 | 06/2023 | [ ] | [ ] | [ ] | [ ] |
| 19 | 09/2023 | [ ] | [ ] | [ ] | [ ] |
| 20 | 12/2023 | [ ] | [ ] | [ ] | [ ] |
| 21 | 03/2024 | [ ] | [ ] | [ ] | [ ] |
| 22 | 06/2024 | [ ] | [ ] | [ ] | [ ] |
| 23 | 09/2024 | [ ] | [ ] | [ ] | [ ] |
| 24 | 12/2024 | [ ] | [ ] | [ ] | [ ] |

**Total:** 24 trimestres × 4 relatórios = **96 downloads**

## Ordem recomendada

Baixe **coluna por coluna**, não linha por linha: fixe o relatório e
percorra os 24 trimestres mudando só a data-base. Alternar entre
relatórios a cada trimestre é mais lento e erra mais.

Ao terminar cada coluna, rode:

```powershell
python testes\organizar_downloads.py --renomear dados\ifdata_bruto\<relatorio> --relatorio <relatorio>
```

Confira o mapeamento na tela e repita com `--aplicar`.

## Registro

| Relatório | Nome exato na interface | Data do download | Trimestres obtidos |
|---|---|---|---|
| resumo | | | /24 |
| ativo | | | /24 |
| resultado | | | /24 |
| segmentacao | | | /24 |

**Ausências e motivo:**

**Observações:**
