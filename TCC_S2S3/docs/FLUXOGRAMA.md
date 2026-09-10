# Fluxograma das operações

Diagramas do pipeline completo: da entrada dos dados às saídas, com as
verificações em cada etapa e o que cada uma bloqueia.

> **Como visualizar.** O VS Code renderiza Mermaid no preview de Markdown
> (`Ctrl+Shift+V`). Para exportar como imagem e inserir no TCC, use a extensão
> *Markdown Preview Mermaid Support* (botão de exportar no diagrama) ou copie o
> bloco em <https://mermaid.live> e baixe em PNG ou SVG.

---

## 1. Visão geral

```mermaid
flowchart TD
    A["IF.data / COSIF<br/>Banco Central do Brasil"] --> B["Coleta<br/>144 arquivos CSV<br/>24 trimestres x 6 relatórios"]
    B --> C["Leitura e normalização<br/>ifdata.py"]
    C --> D["Consolidação<br/>52 conceitos contábeis<br/>consolidacao.py"]
    D --> E["Segmentação S2/S3<br/>coluna SR<br/>segmentacao.py"]
    E --> F["Indicadores<br/>21 medidas de risco<br/>indicadores.py"]
    F --> G["Painel tratado<br/>painel.py"]
    G --> H["Modelagem"]
    H --> I["Escores de atipicidade"]
    I --> J["Interpretação e validação"]
    J --> K["Saídas<br/>rankings, decomposição,<br/>pontos de correção"]

    D -.-> X["diagnostico.py<br/>registro de pendências"]
    E -.-> X
    F -.-> X
    G -.-> X
    H -.-> X
    J -.-> X
    X --> K

    style A fill:#e3f2fd,stroke:#1565c0
    style K fill:#e8f5e9,stroke:#2e7d32
    style X fill:#fff3e0,stroke:#e65100
```

A linha pontilhada é o registro de pendências: **toda etapa pode reportar uma
limitação**, e o relatório final consolida todas. Ausência nunca vira zero
silencioso.

---

## 2. Entrada e tratamento dos dados

```mermaid
flowchart TD
    A["dados/ifdata_bruto/<br/>144 arquivos CSV"] --> B{"Nome do arquivo<br/>identifica relatório<br/>e período?"}
    B -->|"não"| B1["Registra pendência<br/>arquivo ignorado"]
    B -->|"sim"| C{"Conteúdo confere<br/>com o nome?"}
    C -->|"não"| C1["COMPROMETE<br/>relatório trocado<br/>ex: Resumo com Segmentação"]
    C -->|"sim"| D["Detecta linhas de cabeçalho<br/>1 a 3 conforme o relatório"]

    D --> E["Nome da coluna =<br/>nível mais profundo preenchido"]
    E --> F["Separa rodapé de legenda<br/>40 linhas com totais agregados"]
    F --> G["Conversão numérica<br/>1.516.147.949 → float<br/>19,26% → 19.26<br/>NA, NA% → ausente"]
    G --> H{"Coluna converteu?"}
    H -->|"não"| H1["COMPROMETE<br/>indicadores derivados<br/>ficam indefinidos"]
    H -->|"sim"| I["Empilha por relatório"]

    I --> J["Extrai conceitos<br/>mapeamento explícito coluna a coluna"]
    J --> K{"Rótulo mudou<br/>ao longo do recorte?"}
    K -->|"sim"| K1["Coalescência<br/>RWA (i) ou (j)<br/>PL (i) ou (j)"]
    K -->|"não"| L["Soma de parcelas<br/>min_count=1"]
    K1 --> L
    L --> M{"Conceito<br/>obrigatório<br/>presente?"}
    M -->|"não"| M1["BLOQUEIA<br/>pipeline não prossegue"]
    M -->|"sim"| N["Painel de conceitos<br/>31.819 obs x 1.629 inst"]

    style A fill:#e3f2fd,stroke:#1565c0
    style N fill:#e8f5e9,stroke:#2e7d32
    style M1 fill:#ffebee,stroke:#c62828
    style C1 fill:#fff3e0,stroke:#e65100
    style H1 fill:#fff3e0,stroke:#e65100
    style B1 fill:#fff3e0,stroke:#e65100
```

---

## 3. Segmentação e construção dos indicadores

```mermaid
flowchart TD
    A["Painel de conceitos<br/>31.819 observações"] --> B{"Existe lista oficial<br/>de segmentação?"}
    B -->|"coluna SR<br/>do relatório Resumo"| C["Segmentação oficial<br/>Res. CMN 4.553/2017"]
    B -->|"ausente"| B1["BLOQUEIA<br/>reconstrução por Exposição/PIB<br/>é aproximação questionável"]

    C --> D["Filtra S2 e S3"]
    D --> E["Amostra do estudo<br/>1.347 obs x 72 instituições<br/>S2: 9 · S3: 66"]

    E --> F["Construção dos indicadores"]
    F --> G["1 LIT<br/>correspondência direta<br/>na literatura"]
    F --> H["9 ADAP<br/>analogia funcional<br/>Beneish, Dechow, Piotroski"]
    F --> I["11 PROP<br/>arcabouço prudencial<br/>Res. 2.682, Basileia"]

    G --> J{"Insumo<br/>disponível?"}
    H --> J
    I --> J
    J -->|"não"| J1["Indicador OMITIDO<br/>e reportado<br/>nunca preenchido com zero"]
    J -->|"sim"| K["Divisão protegida<br/>denominador ≈ 0 → ausente"]
    K --> L["21 indicadores"]

    style A fill:#e3f2fd,stroke:#1565c0
    style L fill:#e8f5e9,stroke:#2e7d32
    style B1 fill:#ffebee,stroke:#c62828
    style J1 fill:#fff3e0,stroke:#e65100
```

**Piso de Basileia**, aplicado dentro de `folga_basileia`:

```mermaid
flowchart LR
    A["Índice de Basileia"] --> B{"TCB é<br/>b3S ou b3C?"}
    B -->|"não"| C["Piso 10,5 p.p.<br/>1.236 obs · 62 inst"]
    B -->|"sim: cooperativa"| D["Faixa 13 a 18 p.p.<br/>111 obs · 10 inst"]
    D --> E["folga_basileia<br/>contra 13"]
    D --> F["folga_basileia_conservadora<br/>contra 18"]
    E --> G{"Índice entre<br/>13 e 18?"}
    F --> G
    G -->|"sim"| H["basileia_zona_incerta = 1<br/>42 obs · 7 instituições"]
    G -->|"não"| I["Conclusão não depende<br/>do ponto da faixa"]
    C --> I

    style A fill:#e3f2fd,stroke:#1565c0
    style H fill:#fff3e0,stroke:#e65100
```

---

## 4. Tratamento do painel e partição

```mermaid
flowchart TD
    A["21 indicadores"] --> B["Filtro de histórico<br/>mínimo 8 trimestres"]
    B --> B1["Reporta viés de sobrevivência<br/>instituições que saíram<br/>são as de maior interesse"]
    B --> C["Descarte de esparsos<br/>ausência acima de 40%"]
    C --> D["Winsorização 1% e 99%<br/>DENTRO de cada trimestre"]
    D --> E["Z-score por pares<br/>mediana e MAD<br/>dentro de segmento e trimestre"]
    E --> F["Normalização rank-gauss<br/>ajustada SÓ no treino"]
    F --> G["Marcação de ausentes<br/>coluna-sombra faltante_x"]

    G --> H["Partição cronológica"]
    H --> I["Treino<br/>2019 a 2022"]
    H --> J["Validação<br/>2023"]
    H --> K["Teste<br/>2024"]

    I --> L{"Sobreposição<br/>temporal?"}
    J --> L
    K --> L
    L -->|"sim"| L1["BLOQUEIA<br/>divisão aleatória vaza o futuro<br/>em dados de painel"]
    L -->|"não"| M["Matriz X<br/>pronta para os modelos"]

    style A fill:#e3f2fd,stroke:#1565c0
    style M fill:#e8f5e9,stroke:#2e7d32
    style L1 fill:#ffebee,stroke:#c62828
    style B1 fill:#fff3e0,stroke:#e65100
```

**Por que cada decisão:** winsorizar por trimestre preserva a comparação
transversal, já que as contas mudam de escala ao longo do período; o z-score
por pares faz a pergunta ser *"destoa dos pares agora?"* em vez de *"destoa da
população inteira?"*; ajustar a normalização só no treino evita que o modelo
veja a distribuição do futuro; e marcar ausentes impede que a média imputada
faça a ausência parecer normalidade.

---

## 5. Modelagem

```mermaid
flowchart TD
    A["Matriz X"] --> B["Modelos não supervisionados"]
    A --> C["Modelos supervisionados"]

    B --> D["Autoencoder denoising<br/>p → 64 → 32 → 8 → 32 → 64 → p<br/>5 sementes"]
    B --> E["GRU sequencial<br/>janela de 4 trimestres<br/>prevê o seguinte"]
    B --> F["Baselines<br/>PCA · Mahalanobis robusto<br/>Isolation Forest"]

    C --> G{"Guarda de<br/>circularidade"}
    G -->|"atributo é componente<br/>do rótulo"| G1["REMOVE ou BLOQUEIA<br/>senão o modelo apenas<br/>reaprende a fórmula"]
    G -->|"limpo"| H["XGBoost e LightGBM<br/>rótulo fraco"]

    D --> I["Erro de reconstrução<br/>atipicidade transversal"]
    E --> J["Erro de previsão<br/>quebra estrutural"]
    F --> K["Escores de comparação"]
    H --> L["Probabilidades<br/>com e sem os componentes"]

    I --> M{"Estabilidade<br/>entre sementes<br/>≥ 0,80?"}
    M -->|"não"| M1["COMPROMETE<br/>ranking depende da inicialização<br/>nenhuma instituição<br/>pode ser apontada"]
    M -->|"sim"| N["Escore final<br/>mediana entre sementes"]

    style A fill:#e3f2fd,stroke:#1565c0
    style N fill:#e8f5e9,stroke:#2e7d32
    style G1 fill:#ffebee,stroke:#c62828
    style M1 fill:#fff3e0,stroke:#e65100
```

---

## 6. Avaliação e verificações

```mermaid
flowchart TD
    A["Escores"] --> B["Validação por eventos públicos"]
    A --> C["Coerência interna"]
    A --> D["Triangulação independente"]
    A --> E["Comparação entre métodos"]

    B --> B1{"eventos_publicos.csv<br/>preenchido?"}
    B1 -->|"não"| B2["BLOQUEIA<br/>sem eventos, a conclusão<br/>fica restrita a atipicidade"]
    B1 -->|"sim"| B3["Precision@k · Recall@k<br/>ganho sobre o acaso<br/>trimestres de antecedência"]
    B3 --> B4{"Positivos<br/>≥ 10?"}
    B4 -->|"não"| B5["COMPROMETE<br/>reportar como estudo de caso<br/>não como avaliação estatística"]

    C --> C1["Estabilidade entre sementes"]
    C --> C2["Persistência trimestral<br/>Spearman entre trimestres"]
    C2 --> C3{"≥ 0,30?"}
    C3 -->|"não"| C4["COMPROMETE<br/>escore mede ruído,<br/>não condição da instituição"]

    D --> D1["Lei de Newcomb-Benford<br/>dígitos dos saldos publicados"]
    D1 --> D2["MAD e limiares de Nigrini"]
    D2 --> D3["Independente dos indicadores<br/>corroboração genuína"]

    E --> E1["Concordância de posto<br/>rede x PCA x Mahalanobis"]
    E1 --> E2{"Rede concorda<br/>muito com PCA?"}
    E2 -->|"sim"| E3["A não linearidade<br/>não está comprando nada"]
    E2 -->|"não"| E4["Explicar caso a caso<br/>o que a rede vê a mais"]

    style A fill:#e3f2fd,stroke:#1565c0
    style B2 fill:#ffebee,stroke:#c62828
    style B5 fill:#fff3e0,stroke:#e65100
    style C4 fill:#fff3e0,stroke:#e65100
```

Tanto `E3` quanto `E4` são resultados publicáveis. O que não é aceitável é
**não fazer a comparação**.

---

## 7. Saídas

```mermaid
flowchart TD
    A["Pipeline executado"] --> B["dados/tratados/"]
    A --> C["resultados/"]
    A --> D["dados/externos/"]

    B --> B1["painel_conceitos_completo.csv<br/>1.629 instituições"]
    B --> B2["painel_conceitos_S2S3.csv<br/>recorte da pesquisa"]
    B --> B3["painel_indicadores_S2S3.csv<br/>entrada da modelagem"]
    B --> B4["cobertura_conceitos.csv<br/>ausência por conceito"]
    B --> B5["inventario_arquivos.csv<br/>o que foi lido e de onde"]
    B --> B6["quadro_operacionalizacao.csv<br/>ANEXO DO TCC"]
    B --> B7["pontos_de_correcao.csv<br/>pendências da execução"]

    C --> C1["escores_atipicidade.csv<br/>ranking instituição x trimestre"]
    C --> C2["decomposicao_erro.csv<br/>por que cada uma é atípica"]
    C --> C3["ranking_atributos.csv<br/>quais indicadores explicam"]

    D --> D1["segmentacao_oficial.csv<br/>enquadramento S1-S5"]

    C2 --> E["Narrativa auditável<br/>difere dos pares principalmente em<br/>cobertura_provisao, 41% do erro"]
    C3 --> F{"Topo dominado<br/>por indicadores PROP?"}
    F -->|"sim"| G["A adaptação ao contexto bancário<br/>foi o que produziu informação"]
    F -->|"não"| H["A transposição dos modelos<br/>originais bastou"]

    style A fill:#e3f2fd,stroke:#1565c0
    style B6 fill:#e8f5e9,stroke:#2e7d32
    style E fill:#e8f5e9,stroke:#2e7d32
    style G fill:#e8f5e9,stroke:#2e7d32
```

O teste em `F` é o achado metodológico mais forte que o desenho pode entregar:
responde se os indicadores prudenciais propostos carregam informação que a
simples transposição de modelos de empresa não financeira não carregaria.

---

## 8. Testes automatizados

```mermaid
flowchart LR
    A["testes/test_pipeline.py<br/>14 testes"] --> B["Mapeamento<br/>resolve conceitos"]
    A --> C["Indicadores<br/>constroem e declaram ausências"]
    A --> D["Sem insumo<br/>NÃO inventa zero"]
    A --> E["Partição<br/>sem sobreposição temporal"]
    A --> F["Escalador<br/>ajusta só no treino"]
    A --> G["Guarda de circularidade<br/>remove derivações"]
    A --> H["Rede treina<br/>e produz escore estável"]
    A --> I["Sequências e GRU"]
    A --> J["Baselines e concordância"]
    A --> K["Avaliação por eventos"]
    A --> L["Rótulo fraco<br/>declara componentes"]
    A --> M["Benford classifica"]
    A --> N["Narrativa<br/>NÃO afirma fraude"]
    A --> O["Diagnóstico<br/>produz relatório"]

    style A fill:#e3f2fd,stroke:#1565c0
```

Os testes `D` e `N` merecem destaque: o primeiro garante que indicador sem
insumo é omitido e reportado, nunca preenchido com zero; o segundo garante que
o texto gerado fala em *atipicidade* e nunca em *fraude*. São verificações de
integridade metodológica, não apenas de funcionamento.

Ferramentas auxiliares, fora da suíte:

| Script | Função |
|---|---|
| `testes/diagnostico_rede.py` | Acesso ao IF.data: DNS, TCP, TLS, HTTP |
| `testes/validar_extracao_manual.py` | Cobertura, duplicidade, formato, colunas |
| `testes/organizar_downloads.py` | Renomeia downloads pela ordem cronológica |
| `processar_base.py` | Executa o tratamento completo |

---

## 9. Legenda das severidades

| Marca | Significado |
|---|---|
| **BLOQUEIA** | Os escores não devem ser reportados no TCC enquanto não resolvido |
| **COMPROMETE** | Pode ser reportado, com ressalva explícita no texto |
| **OBSERVAÇÃO** | Transparência; não invalida nada |

Ausência de pendências não equivale a validação metodológica — significa apenas
que nenhuma verificação automatizada falhou.
