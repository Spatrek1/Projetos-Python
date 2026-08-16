"""Ponte entre as colunas do IF.data e os conceitos contábeis do estudo.

Por que existe
--------------
O IF.data não entrega contas COSIF cruas: entrega relatórios já montados
(Resumo, Ativo, Passivo, DRE, Carteira por nível de risco, Capital, ...) cujos
rótulos de coluna mudam entre relatórios e ao longo do tempo. Codificar
``df["Operações de Crédito"]`` é frágil e, pior, silencioso: um rótulo
diferente vira ``KeyError`` ou, em pivots, vira coluna vazia.

Aqui cada conceito é declarado por **padrões de reconhecimento** (regex sobre
o rótulo normalizado, sem acento e sem pontuação) e por sua **origem
normativa**. A resolução é feita contra os rótulos que realmente vieram, e
tudo que não resolver é reportado como ponto de correção.

Fonte normativa dos conceitos: Plano Contábil das Instituições do Sistema
Financeiro Nacional (COSIF); classificação de risco de crédito e provisão
conforme Resolução CMN nº 2.682/1999; capital regulatório conforme o arcabouço
de Basileia adotado pelo BCB.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

from . import diagnostico

AREA = "mapeamento/cosif"


@dataclass(frozen=True)
class Conceito:
    """Um conceito contábil buscado nos relatórios do IF.data."""

    chave: str
    descricao: str
    padroes: tuple[str, ...]          # regex sobre rótulo normalizado
    obrigatorio: bool                 # se ausente, bloqueia o pipeline
    natureza: str                     # "estoque" (saldo) ou "fluxo" (resultado)
    observacao: str = ""


#: Conceitos mínimos para reconstruir os indicadores do estudo.
#: A lista é intencionalmente enxuta: cada conceito adicional é uma chance a
#: mais de mapeamento errado, e mapeamento errado contamina todos os modelos.
CONCEITOS: tuple[Conceito, ...] = (
    # ---------------------------- Balanço ---------------------------------
    Conceito("ativo_total", "Ativo total",
             (r"^ativo(total)?$", r"ativototal", r"totaldoativo"), True, "estoque"),
    Conceito("disponibilidades", "Disponibilidades e aplicações interfinanceiras de liquidez",
             (r"disponibilidade", r"aplicac(oes)?interfinanceira", r"caixa"), False, "estoque"),
    Conceito("tvm", "Títulos e valores mobiliários e instrumentos financeiros derivativos",
             (r"titulos?evalores", r"^tvm", r"valoresmobiliarios"), False, "estoque",
             "Analogo funcional do 'estoque' nos modelos originais (ativo de giro)."),
    Conceito("carteira_credito", "Operações de crédito (carteira classificada)",
             (r"operac(oes)?decredito", r"carteiradecredito", r"^credito$",
              r"carteiraclassificada"), True, "estoque"),
    Conceito("provisao_pcld", "Provisão para créditos de liquidação duvidosa (saldo)",
             (r"provisa[oõ].*credito", r"^pcld", r"provisa[oõ]paracredito",
              r"provisa[oõ]operac(oes)?decredito"), True, "estoque"),
    Conceito("carteira_eh", "Carteira classificada nos níveis E a H (Res. 2.682)",
             (r"nivel(is)?[eh]", r"^[eh]$", r"classificac(ao)?deh", r"eah$"), False, "estoque",
             "Se ausente, o teste de suficiencia de provisao perde a referencia direta."),
    Conceito("outros_creditos", "Outros créditos e outros valores e bens",
             (r"outroscreditos", r"outrosvaloresebens", r"outrosativos"), False, "estoque"),
    Conceito("creditos_tributarios", "Créditos tributários (ativo fiscal diferido)",
             (r"creditotributario", r"creditostributarios", r"ativofiscaldiferido",
              r"tributariodiferido"), False, "estoque",
             "Componente de baixa qualidade de capital; sensivel a manipulacao."),
    Conceito("imobilizado", "Imobilizado de uso",
             (r"imobilizado", r"ativopermanente", r"^permanente$"), False, "estoque"),
    Conceito("intangivel", "Intangível e ágio",
             (r"intangivel", r"agio", r"goodwill"), False, "estoque"),
    Conceito("captacoes", "Captações / depósitos totais",
             (r"captac(oes)?", r"depositos?total", r"^depositos$",
              r"recursoscaptados"), False, "estoque"),
    Conceito("passivo_total", "Passivo total (exigível)",
             (r"^passivototal$", r"totaldopassivo", r"^passivocirculante"), False, "estoque",
             "No relatorio Resumo do IF.data o rotulo observado e 'Passivo Circulante e "
             "Exigivel a Longo Prazo e Resultados de Exercicios Futuros'."),
    Conceito("patrimonio_liquido", "Patrimônio líquido",
             (r"patrimonioliquido", r"^pl$"), True, "estoque"),
    Conceito("capital_social", "Capital social realizado",
             (r"capitalsocial", r"capitalrealizado"), False, "estoque",
             "Base do indicador de emissao de capital (analogo a EQ_OFFER)."),

    # ------------------------- Resultado (DRE) -----------------------------
    Conceito("lucro_liquido", "Lucro líquido do período",
             (r"lucroliquido", r"resultadoliquido", r"^lucro$",
              r"resultadodoperiodo", r"resultadorecorrente"), True, "fluxo"),
    Conceito("receita_intermediacao", "Receitas da intermediação financeira",
             (r"receit.*intermediacao", r"rendasdeoperac(oes)?decredito"), False, "fluxo"),
    Conceito("despesa_intermediacao", "Despesas da intermediação financeira",
             (r"despesa.*intermediacao", r"despesasdecaptacao"), False, "fluxo"),
    Conceito("resultado_intermediacao", "Resultado bruto da intermediação financeira",
             (r"resultado.*intermediacao", r"margemfinanceira",
              r"resultadobrutointermediacao"), True, "fluxo",
             "Analogo funcional da margem bruta (GMI de Beneish) em banco."),
    Conceito("despesa_provisao", "Despesa de provisão para crédito no período",
             (r"despesa.*provisa", r"provisa[oõ].*despesa", r"resultadodeprovisa"),
             False, "fluxo",
             "Variavel central: subprovisionar e o mecanismo mais direto de "
             "inflar resultado em instituicao financeira."),
    Conceito("receita_servicos", "Rendas de prestação de serviços e tarifas",
             (r"prestacaodeservicos", r"tarifas?bancarias?", r"rendasdeservicos"),
             False, "fluxo"),
    Conceito("despesa_administrativa", "Despesas administrativas e de pessoal",
             (r"despesa.*administrativ", r"despesa.*pessoal", r"despesasoperacionais"),
             False, "fluxo"),
    Conceito("outras_receitas_op", "Outras receitas/despesas operacionais",
             (r"outrasreceita", r"outrasdespesa", r"outrasreceitasedespesas"),
             False, "fluxo",
             "Concentracao de resultado nesta linha e sinal classico de resultado "
             "nao recorrente."),

    # ---------------------- Capital e qualidade ----------------------------
    Conceito("indice_basileia", "Índice de Basileia (capital total / RWA)",
             (r"indicedebasileia", r"^basileia", r"indicedecapitaltotal",
              r"razaodealavancagem"), False, "estoque"),
    Conceito("patrimonio_referencia", "Patrimônio de referência (PR)",
             (r"patrimoniodereferencia", r"^pr$", r"capitaltotal"), False, "estoque"),
    Conceito("rwa", "Ativos ponderados pelo risco (RWA)",
             (r"^rwa", r"ativosponderados", r"exposicaototalaorisco"), False, "estoque"),
    Conceito("inadimplencia", "Índice de inadimplência (atraso > 90 dias)",
             (r"inadimplencia", r"atrasoacimade90", r"vencidasacimade90"), False, "estoque"),
)


CONCEITOS_POR_CHAVE = {c.chave: c for c in CONCEITOS}


# ---------------------------------------------------------------------------

def normalizar(rotulo: str) -> str:
    """Minúsculas, sem acento, sem pontuação nem espaço."""
    s = unicodedata.normalize("NFKD", str(rotulo))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", s.lower())


@dataclass
class Mapeamento:
    """Resultado da resolução: conceito -> rótulo real encontrado."""

    resolvidos: dict[str, str]
    ambiguos: dict[str, list[str]]
    ausentes: list[str]
    rotulos_nao_usados: list[str]

    @property
    def cobertura(self) -> float:
        return len(self.resolvidos) / len(CONCEITOS)

    def tabela(self) -> pd.DataFrame:
        linhas = []
        for c in CONCEITOS:
            linhas.append(
                {
                    "conceito": c.chave,
                    "descricao": c.descricao,
                    "obrigatorio": c.obrigatorio,
                    "situacao": (
                        "resolvido" if c.chave in self.resolvidos
                        else "ambiguo" if c.chave in self.ambiguos
                        else "ausente"
                    ),
                    "rotulo_no_ifdata": self.resolvidos.get(
                        c.chave, " | ".join(self.ambiguos.get(c.chave, []))[:80]
                    ),
                }
            )
        return pd.DataFrame(linhas)


def resolver(rotulos: list[str], preferencias: dict[str, str] | None = None) -> Mapeamento:
    """Casa os rótulos observados com os conceitos declarados.

    ``preferencias`` permite fixar manualmente um conceito -> rótulo, o que é
    o caminho normal de correção depois que o diagnóstico apontar ambiguidade.
    """
    preferencias = preferencias or {}
    normalizados = {r: normalizar(r) for r in rotulos}

    resolvidos: dict[str, str] = {}
    ambiguos: dict[str, list[str]] = {}
    ausentes: list[str] = []

    for c in CONCEITOS:
        if c.chave in preferencias:
            escolhido = preferencias[c.chave]
            if escolhido in rotulos:
                resolvidos[c.chave] = escolhido
                continue

        candidatos = [
            r for r, n in normalizados.items()
            if any(re.search(p, n) for p in c.padroes)
        ]
        if len(candidatos) == 1:
            resolvidos[c.chave] = candidatos[0]
        elif len(candidatos) > 1:
            # desempate: o rótulo mais curto tende a ser a conta sintética
            # (ex.: "Ativo Total" vence "Ativo Total Ajustado Médio")
            candidatos.sort(key=lambda r: (len(normalizados[r]), r))
            ambiguos[c.chave] = candidatos
            resolvidos[c.chave] = candidatos[0]
        else:
            ausentes.append(c.chave)

    usados = set(resolvidos.values())
    nao_usados = [r for r in rotulos if r not in usados]

    mapa = Mapeamento(resolvidos, ambiguos, ausentes, nao_usados)
    _diagnosticar(mapa)
    return mapa


def _diagnosticar(mapa: Mapeamento) -> None:
    obrigatorios_ausentes = [
        k for k in mapa.ausentes if CONCEITOS_POR_CHAVE[k].obrigatorio
    ]
    if obrigatorios_ausentes:
        diagnostico.registrar(
            area=AREA,
            item=(
                "Conceitos contabeis obrigatorios nao encontrados nos relatorios "
                f"coletados: {obrigatorios_ausentes}."
            ),
            impacto=(
                "Indicadores que dependem desses conceitos ficam indefinidos, e a "
                "rede passa a operar sobre um espaco de atributos diferente do "
                "descrito na metodologia do TCC."
            ),
            acao=(
                "Incluir na coleta o relatorio do IF.data que contem essas contas "
                "(tipicamente 'Balanco Patrimonial Ativo/Passivo' e 'Demonstracao "
                "de Resultado'), ou fixar o rotulo correto via "
                "mapeamento.resolver(..., preferencias={'conceito': 'Rotulo Real'})."
            ),
            severidade=diagnostico.Severidade.BLOQUEIA,
        )

    opcionais_ausentes = [
        k for k in mapa.ausentes if not CONCEITOS_POR_CHAVE[k].obrigatorio
    ]
    if opcionais_ausentes:
        diagnostico.registrar(
            area=AREA,
            item=f"Conceitos opcionais ausentes: {opcionais_ausentes}.",
            impacto=(
                "Os indicadores derivados desses conceitos sao omitidos do painel. "
                "Em particular, a ausencia de 'carteira_eh' e 'despesa_provisao' "
                "retira do modelo o canal de manipulacao mais documentado em banco "
                "(subprovisionamento)."
            ),
            acao=(
                "Verificar no IF.data se ha relatorio especifico ('Carteira de credito "
                "por nivel de risco', 'Informacoes de capital') e inclui-lo na coleta. "
                "Caso realmente nao exista para o recorte, declarar a limitacao na "
                "secao 3.2.4 do TCC."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )

    if mapa.ambiguos:
        diagnostico.registrar(
            area=AREA,
            item=f"Rotulos ambiguos resolvidos por heuristica: {sorted(mapa.ambiguos)}.",
            impacto=(
                "A escolha automatica pode ter selecionado uma conta analitica no lugar "
                "da sintetica (ou saldo medio no lugar de saldo final), deslocando a "
                "escala dos indicadores."
            ),
            acao=(
                "Conferir a coluna 'rotulo_no_ifdata' da tabela de mapeamento e fixar a "
                "escolha correta em `preferencias`. Anexar a tabela final ao TCC como "
                "quadro de operacionalizacao das variaveis."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )


def aplicar(df: pd.DataFrame, mapa: Mapeamento) -> pd.DataFrame:
    """Renomeia as colunas do painel largo para as chaves de conceito."""
    inverso = {rotulo: chave for chave, rotulo in mapa.resolvidos.items()}
    saida = df.rename(columns=inverso)
    manter = [c for c in saida.columns if c in CONCEITOS_POR_CHAVE or c in
              ("cod_inst", "instituicao", "anomes", "segmento", "cnpj", "tipo_instituicao")]
    return saida[manter]
