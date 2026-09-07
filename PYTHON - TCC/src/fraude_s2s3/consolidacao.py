"""Consolidação dos relatórios do IF.data em painel único de conceitos contábeis.

Entrada
-------
Árvore de diretórios com as exportações CSV do IF.data, organizada por ano e
trimestre, com seis relatórios por data-base::

    IF DATA BASE/2019/201903/dados 2019-03 Ativo.csv
                            /dados 2019-03 DRE.csv
                            /dados 2019-03 Info de Cap.csv
                            /dados 2019-03 Passivo.csv
                            /dados 2019-03 Resumo.csv
                            /dados 2019-03 Segmentação.csv

Saída
-----
Painel largo com uma linha por (instituição, trimestre) e uma coluna por
conceito contábil, restrito aos segmentos alvo.

Princípio
---------
O mapeamento aqui é **explícito**, coluna a coluna, e não por reconhecimento de
padrão. Os rótulos reais do IF.data são conhecidos e estáveis dentro de cada
relatório; nomear cada conta expressamente elimina a chance de um casamento
aproximado escolher a conta errada — risco real quando existem, no mesmo
relatório, "Operações de Crédito (d1)", "Provisão sobre Operações de Crédito
(d2)" e "Operações de Crédito Líquidas de Provisão (d)".

Nenhum valor é criado, imputado ou alterado. Conta ausente permanece ausente e
é reportada em :mod:`fraude_s2s3.diagnostico`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import diagnostico, ifdata

AREA = "consolidacao/ifdata"

#: Convenção de sinais do IF.data, verificada nos arquivos:
#: provisões e despesas vêm com sinal negativo, de modo que a identidade
#: contábil se fecha por soma — ex.: Operações de Crédito (d1) + Provisão (d2)
#: = Operações Líquidas (d). Os indicadores que exigem magnitude aplicam
#: valor absoluto explicitamente, e isso está documentado em cada fórmula.
SINAL_NEGATIVO = ("provisao_pcld", "despesa_provisao", "despesa_intermediacao",
                  "despesa_pessoal", "despesa_administrativa", "despesa_tributaria",
                  "ir_csll", "participacao_lucros")


@dataclass(frozen=True)
class Fonte:
    """De onde vem um conceito: relatório e coluna(s) a somar."""

    relatorio: str
    colunas: tuple[str, ...]
    obrigatorio: bool = False
    nota: str = ""


#: Mapeamento conceito -> origem. Rótulos conforme observados nas exportações
#: de 2019-03 a 2024-12 (tipo de instituição: Conglomerados Prudenciais e
#: Instituições Independentes).
MAPA: dict[str, Fonte] = {
    # ------------------------------- Ativo -------------------------------
    "ativo_total": Fonte("ativo", ("Ativo Total (k) = (i) - (j)",), True),
    "ativo_total_ajustado": Fonte(
        "ativo", ("Ativo Total Ajustado (i) = (a) + (b) + (c) + (d) + (e) + (f) + (g) + (h)",)),
    "disponibilidades": Fonte(
        "ativo", ("Disponibilidades (a)", "Aplicações Interfinanceiras de Liquidez (b)"),
        nota="Soma de caixa e aplicações interfinanceiras de liquidez."),
    "tvm": Fonte("ativo", ("TVM e Instrumentos Financeiros Derivativos (c)",)),
    "carteira_credito": Fonte("ativo", ("Operações de Crédito (d1)",), True,
                              "Carteira bruta, antes da provisão."),
    "provisao_pcld": Fonte("ativo", ("Provisão sobre Operações de Crédito (d2)",), True,
                           "Vem com sinal negativo no IF.data."),
    "carteira_liquida": Fonte("ativo", ("Operações de Crédito Líquidas de Provisão (d)",)),
    "arrendamento": Fonte("ativo", ("Arrendamento Mercantil Líquido de Provisão (e)",)),
    "outros_creditos": Fonte("ativo", ("Outros Créditos - Líquido de Provisão (f)",
                                       "Outros Ativos Realizáveis (g)")),
    "permanente": Fonte("ativo", ("Permanente Ajustado (h)",),
                        nota="Inclui imobilizado e intangível; o IF.data não os separa."),

    # ------------------------------ Passivo ------------------------------
    "depositos_vista": Fonte("passivo", ("Depósitos à Vista (a1)",)),
    "depositos_prazo": Fonte("passivo", ("Depósitos a Prazo (a4)",)),
    "depositos_total": Fonte("passivo", ("Depósito Total (a)",)),
    "compromissadas": Fonte("passivo", ("Obrigações por Operações Compromissadas (b)",)),
    "letras_financeiras": Fonte("passivo", ("Letras Financeiras (c3)",)),
    "captacoes": Fonte("passivo", ("Captações (e) = (a) + (b) + (c) + (d)",)),
    "depositos_outros": Fonte("passivo", ("Depósitos Outros (a6)",)),
    "passivo_total": Fonte("passivo", ("Passivo Total (k) = (h) + (i) + (j)",
                                       "Passivo Total (j) = (h) + (i)")),
    "resultados_exerc_futuros": Fonte(
        "passivo", ("Resultados de Exercícios Futuros (i)",),
        nota="Deixa de ser publicado a partir de 2023-09."),
    "outras_obrigacoes": Fonte("passivo", ("Outras Obrigações (g)",)),
    "passivo_exigivel": Fonte(
        "passivo", ("Passivo Circulante e Exigível a Longo Prazo (h) = (e) + (f) + (g)",)),
    "patrimonio_liquido": Fonte("passivo", ("Patrimônio Líquido (i)",), True),

    # -------------------------------- DRE --------------------------------
    "rendas_credito": Fonte("dre", ("Rendas de Operações de Crédito (a1)",)),
    "rendas_tvm": Fonte("dre", ("Rendas de Operações com TVM (a3)",)),
    "receita_intermediacao": Fonte(
        "dre", ("Receitas de Intermediação Financeira (a) = (a1) + (a2) + (a3) + (a4) + (a5) + (a6)",)),
    "despesa_captacao": Fonte("dre", ("Despesas de Captação (b1)",)),
    "despesa_provisao": Fonte(
        "dre", ("Resultado de Provisão para Créditos de Difícil Liquidação (b5)",),
        nota="Sinal negativo. É a despesa de provisão do período."),
    "despesa_intermediacao": Fonte(
        "dre", ("Despesas de Intermediação Financeira (b) = (b1) + (b2) + (b3) + (b4) + (b5)",)),
    "resultado_intermediacao": Fonte(
        "dre", ("Resultado de Intermediação Financeira (c) = (a) + (b)",), True),
    "receita_servicos": Fonte("dre", ("Rendas de Prestação de Serviços (d1)",
                                      "Rendas de Tarifas Bancárias (d2)")),
    "despesa_pessoal": Fonte("dre", ("Despesas de Pessoal (d3)",)),
    "despesa_administrativa": Fonte("dre", ("Despesas Administrativas (d4)",)),
    "despesa_tributaria": Fonte("dre", ("Despesas Tributárias (d5)",)),
    "outras_receitas_op": Fonte("dre", ("Outras Receitas Operacionais (d7)",)),
    "outras_despesas_op": Fonte("dre", ("Outras Despesas Operacionais (d8)",)),
    "resultado_operacional": Fonte("dre", ("Resultado Operacional (e) = (c) + (d)",)),
    "resultado_nao_operacional": Fonte("dre", ("Resultado Não Operacional (f)",)),
    "resultado_antes_trib": Fonte(
        "dre", ("Resultado antes da Tributação, Lucro e Participação (g) = (e) + (f)",)),
    "ir_csll": Fonte("dre", ("Imposto de Renda e Contribuição Social (h)",)),
    "lucro_liquido": Fonte("dre", ("Lucro Líquido (j) = (g) + (h) + (i)",), True),

    # -------------------------- Informações de capital -------------------
    "capital_principal": Fonte("info_cap", ("Capital Principal para Comparação com RWA (a)",)),
    "patrimonio_referencia": Fonte("info_cap", ("Patrimônio de Referência para Comparação com o RWA",)),
    "rwa": Fonte("info_cap", ("Ativos Ponderados pelo Risco (RWA) (j) = (f) + (g) + (h) + (i)",)),
    "rwa_credito": Fonte("info_cap", ("RWA para Risco de Crédito (f)",)),
    "indice_basileia": Fonte("info_cap", ("Índice de Basileia (n) = (e) / (j)",)),
    "indice_capital_principal": Fonte("info_cap", ("Índice de Capital Principal (l) = (a) / (j)",)),
    "adicional_capital": Fonte("info_cap", ("Adicional de Capital Principal",)),
    "indice_imobilizacao": Fonte("info_cap", ("Índice de Imobilização (p)",)),

    # ------------------------------- Resumo ------------------------------
    "carteira_classificada": Fonte("resumo", ("Carteira de Crédito Classificada",),
                                   nota="Difere da carteira contábil do relatório Ativo."),
    "numero_agencias": Fonte("resumo", ("Número de Agências",)),

    # ---------------------------- Segmentação ----------------------------
    "exposicao_total": Fonte("segmentacao", ("Exposição Total ou Ativo Total (R$ mil)",)),
    "ativos_exterior_usd": Fonte("segmentacao", ("Total de Ativos Consolidados no Exterior (US$ mil)",)),
}

#: Rótulos que variaram ao longo do recorte, levantados arquivo a arquivo nos
#: 24 trimestres. As letras de referência entre parênteses mudam quando o BCB
#: acrescenta uma parcela ao cálculo — por exemplo, o RWA passa de
#: "(i) = (f) + (g) + (h)" para "(j) = (f) + (g) + (h) + (i)" com a inclusão do
#: RWAsp. São variantes do MESMO conceito e nunca coexistem no mesmo trimestre;
#: por isso são combinadas por coalescência, não por soma.
ALTERNATIVAS: dict[str, tuple[str, ...]] = {
    "patrimonio_liquido": ("Patrimônio Líquido (j)", "Patrimônio Líquido (i)"),
    "passivo_exigivel": (
        "Passivo Circulante e Exigível a Longo Prazo e Resultados de Exercícios Futuros",
    ),
    "patrimonio_referencia": ("Patrimônio de Referência para Comparação com o RWA (e)",),
    "rwa": ("Ativos Ponderados pelo Risco (RWA) (i) = (f) + (g) + (h)",),
    "indice_basileia": ("Índice de Basileia (m) = (e) / (i)",),
    "indice_capital_principal": ("Índice de Capital Principal (k) = (a) / (i)",),
    "indice_imobilizacao": ("Índice de Imobilização (o)",),
    "depositos_outros": ("Outros Depósitos (a5)",),
}

RELATORIOS = ("ativo", "dre", "info_cap", "passivo", "resumo", "segmentacao")
CHAVES = ("cod_inst", "anomes")
METADADOS = ("Instituição", "TCB", "SR", "TD", "TC", "Cidade", "UF")


# ---------------------------------------------------------------------------
# Inventário
# ---------------------------------------------------------------------------

def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return t.replace("#U00e7", "c").replace("#U00e3", "a").lower()


def identificar_relatorio(nome: str) -> str | None:
    """Deduz o relatório pelo nome do arquivo, tolerando variações de grafia.

    Os nomes observados na base incluem 'Info de Cap', 'Info de cap',
    'Info cap' e 'Info Cap' para o mesmo relatório.
    """
    n = _sem_acento(nome)
    if "ativo" in n:
        return "ativo"
    if "dre" in n or "resultado" in n:
        return "dre"
    if "cap" in n:
        return "info_cap"
    if "passivo" in n:
        return "passivo"
    if "segmenta" in n:
        return "segmentacao"
    if "resumo" in n:
        return "resumo"
    return None


def identificar_periodo(nome: str) -> int | None:
    """Extrai AAAAMM do nome, aceitando mês com um ou dois dígitos."""
    m = re.search(r"(20\d{2})\D{1,2}(\d{1,2})(?!\d)", nome)
    if not m:
        return None
    ano, mes = int(m.group(1)), int(m.group(2))
    return ano * 100 + mes if 1 <= mes <= 12 else None


def inventariar(diretorio: Path | str) -> pd.DataFrame:
    """Lista os arquivos encontrados, com relatório e período deduzidos."""
    diretorio = Path(diretorio)
    linhas = []
    for p in sorted(diretorio.rglob("*.csv")):
        linhas.append({
            "arquivo": p.name,
            "caminho": str(p),
            "relatorio": identificar_relatorio(p.stem),
            "anomes": identificar_periodo(p.stem),
            "bytes": p.stat().st_size,
        })
    return pd.DataFrame(linhas)


def _conferir_conteudo(inv: pd.DataFrame) -> pd.DataFrame:
    """Verifica se o conteúdo do arquivo corresponde ao relatório do nome.

    Um arquivo salvo com o nome de um relatório e o conteúdo de outro é o erro
    de download mais difícil de perceber: o pipeline leria colunas inexistentes
    e produziria ausências em cadeia, sem que a origem ficasse evidente.
    """
    assinaturas = {
        "ativo": "Disponibilidades",
        "dre": "Rendas de Operações de Crédito",
        "info_cap": "Capital Principal",
        "passivo": "Depósitos à Vista",
        "resumo": "Carteira de Crédito Classificada",
        "segmentacao": "Instituição Sujeita à Apuração",
    }
    conferido = []
    for _, r in inv.iterrows():
        real = None
        try:
            with open(r["caminho"], encoding="utf-8-sig", errors="replace") as fh:
                topo = "".join(fh.readline() for _ in range(4))
            for rel, marca in assinaturas.items():
                if marca in topo:
                    real = rel
                    break
        except Exception:
            real = "ilegivel"
        conferido.append(real)
    inv = inv.copy()
    inv["relatorio_no_conteudo"] = conferido
    inv["divergente"] = inv["relatorio"] != inv["relatorio_no_conteudo"]
    return inv


# ---------------------------------------------------------------------------
# Consolidação
# ---------------------------------------------------------------------------

@dataclass
class Consolidado:
    conceitos: pd.DataFrame
    inventario: pd.DataFrame
    cobertura: pd.DataFrame
    ausentes: dict[str, list[str]] = field(default_factory=dict)


def _extrair(df: pd.DataFrame, chave: str, fonte: Fonte) -> pd.Series | None:
    """Constrói o conceito a partir das colunas declaradas.

    Duas operações distintas, deliberadamente separadas:

    **Soma** entre as colunas de ``fonte.colunas`` — são parcelas
    semanticamente diferentes do mesmo conceito (disponibilidades = caixa +
    aplicações interfinanceiras). Usa ``min_count=1``: linha sem nenhuma
    parcela permanece ausente em vez de virar zero.

    **Coalescência** com ``ALTERNATIVAS[chave]`` — são variantes de rótulo do
    mesmo conceito, que mudam ao longo do recorte e nunca coexistem no mesmo
    trimestre. Somá-las duplicaria o valor; a coalescência preenche apenas
    onde a variante principal está ausente.
    """
    presentes = [c for c in fonte.colunas if c in df.columns]

    serie: pd.Series | None = None
    if presentes:
        bloco = df[presentes].apply(pd.to_numeric, errors="coerce")
        serie = bloco.sum(axis=1, min_count=1)

    for alt in ALTERNATIVAS.get(chave, ()):
        if alt not in df.columns:
            continue
        candidata = pd.to_numeric(df[alt], errors="coerce")
        serie = candidata if serie is None else serie.fillna(candidata)

    return serie


def consolidar(diretorio: Path | str, verboso: bool = True) -> Consolidado:
    """Lê todos os relatórios e monta o painel de conceitos contábeis."""
    inv = _conferir_conteudo(inventariar(diretorio))

    divergentes = inv[inv["divergente"] & inv["relatorio"].notna()]
    if len(divergentes):
        detalhe = "; ".join(
            f"{r.arquivo} (nome diz '{r.relatorio}', conteudo e '{r.relatorio_no_conteudo}')"
            for r in divergentes.itertuples()
        )
        diagnostico.registrar(
            area=AREA,
            item=f"{len(divergentes)} arquivo(s) com conteudo divergente do nome: {detalhe}",
            impacto=(
                "O relatorio esperado nao existe para aquele trimestre. Os conceitos "
                "dele ficam ausentes na data-base correspondente, e os indicadores de "
                "variacao interanual que dependem deles ficam indefinidos por quatro "
                "trimestres."
            ),
            acao=(
                "Rebaixar o relatorio correto no IF.data para essa data-base e "
                "substituir o arquivo. Area: consolidacao.consolidar()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )

    partes: dict[str, list[pd.DataFrame]] = {r: [] for r in RELATORIOS}
    colunas_vistas: dict[str, set[str]] = {r: set() for r in RELATORIOS}
    falhas: list[str] = []

    validos = inv[inv["relatorio"].notna() & inv["anomes"].notna() & ~inv["divergente"]]
    for r in validos.itertuples():
        try:
            df = ifdata.carregar_ifdata_csv(r.caminho, anomes=int(r.anomes))
        except Exception as e:
            falhas.append(f"{r.arquivo}: {type(e).__name__}: {e}")
            continue
        partes[r.relatorio].append(df)
        colunas_vistas[r.relatorio].update(df.columns)

    if falhas:
        diagnostico.registrar(
            area=AREA,
            item=f"{len(falhas)} arquivo(s) nao puderam ser lidos.",
            impacto="Os trimestres correspondentes ficam ausentes do painel.",
            acao=f"Verificar: {'; '.join(falhas[:5])}. Area: consolidacao.consolidar().",
            severidade=diagnostico.Severidade.COMPROMETE,
        )

    empilhado: dict[str, pd.DataFrame] = {}
    for rel, lista in partes.items():
        if lista:
            empilhado[rel] = pd.concat(lista, ignore_index=True)
            if verboso:
                print(f"  {rel:<13} {len(lista):>3} arquivo(s)  "
                      f"{len(empilhado[rel]):>7,} linhas")

    # Base de identificação: o relatório Ativo, presente em todo o recorte.
    if "ativo" not in empilhado:
        raise ValueError("Relatorio 'ativo' ausente: nao ha base de identificacao.")

    base_cols = ["cod_inst", "anomes"] + [c for c in METADADOS if c in empilhado["ativo"].columns]
    painel = empilhado["ativo"][base_cols].drop_duplicates(CHAVES).copy()

    construidos: list[str] = []
    ausentes: dict[str, list[str]] = {}

    for chave, fonte in MAPA.items():
        origem = empilhado.get(fonte.relatorio)
        if origem is None:
            ausentes.setdefault(fonte.relatorio, []).append(chave)
            continue
        serie = _extrair(origem, chave, fonte)
        if serie is None:
            ausentes.setdefault(fonte.relatorio, []).append(chave)
            continue
        temp = origem[list(CHAVES)].copy()
        temp[chave] = serie.values
        temp = temp.drop_duplicates(CHAVES)
        painel = painel.merge(temp, on=CHAVES, how="left")
        construidos.append(chave)

    faltando_obrig = [k for k, f in MAPA.items() if f.obrigatorio and k not in construidos]
    if faltando_obrig:
        diagnostico.registrar(
            area=AREA,
            item=f"Conceitos obrigatorios nao construidos: {faltando_obrig}",
            impacto="O painel nao sustenta os indicadores centrais do estudo.",
            acao="Conferir os rotulos em consolidacao.MAPA. Area: consolidacao.consolidar().",
            severidade=diagnostico.Severidade.BLOQUEIA,
        )
    if ausentes:
        diagnostico.registrar(
            area=AREA,
            item=f"Conceitos sem coluna correspondente: {ausentes}",
            impacto="Os indicadores derivados ficam indefinidos e serao omitidos.",
            acao=(
                "Conferir se o rotulo mudou ao longo do recorte e acrescentar a variante "
                "em consolidacao.ALTERNATIVAS. Area: consolidacao.consolidar()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )

    cobertura = _medir_cobertura(painel, construidos)
    return Consolidado(conceitos=painel, inventario=inv, cobertura=cobertura, ausentes=ausentes)


def _medir_cobertura(painel: pd.DataFrame, conceitos: list[str]) -> pd.DataFrame:
    linhas = []
    for c in conceitos:
        s = painel[c]
        linhas.append({
            "conceito": c,
            "relatorio": MAPA[c].relatorio,
            "obrigatorio": MAPA[c].obrigatorio,
            "preenchidos": int(s.notna().sum()),
            "ausentes": int(s.isna().sum()),
            "pct_ausente": round(float(s.isna().mean()) * 100, 2),
            "mediana": round(float(s.median()), 2) if s.notna().any() else None,
        })
    return pd.DataFrame(linhas).sort_values("pct_ausente", ascending=False, ignore_index=True)
