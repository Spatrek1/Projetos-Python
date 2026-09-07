"""Coleta no IF.data (Banco Central do Brasil) via serviço OData Olinda.

Princípio de projeto
--------------------
Este módulo **não assume** o esquema do serviço. Nomes de recursos, de
parâmetros e de colunas variam entre versões da API e entre relatórios do
IF.data. Em vez de codificar nomes como se fossem certos, o cliente:

1. baixa o documento ``$metadata`` do serviço;
2. enumera os recursos e parâmetros realmente publicados;
3. só então monta as requisições;
4. registra em :mod:`fraude_s2s3.diagnostico` tudo que não conseguiu resolver.

Se a API estiver indisponível, mudar de contrato, ou o ambiente não tiver
saída de rede, use :func:`carregar_csv_local` com os arquivos exportados
manualmente pela interface web do IF.data. O restante do pipeline é idêntico
nos dois caminhos.

Aviso de reprodutibilidade
--------------------------
Toda resposta bem-sucedida é gravada em ``dados/brutos/`` com o carimbo da
data de coleta. O TCC deve citar essa data: o IF.data admite *republicação*
de períodos anteriores quando a instituição reapresenta documento, de modo
que uma coleta em datas diferentes pode produzir painéis diferentes.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests

from . import diagnostico
from .config import CONFIG, DIR_BRUTOS, ConfigColeta, periodos

AREA = "coleta/ifdata"


class ErroColeta(RuntimeError):
    """Falha de coleta que o pipeline não deve mascarar."""


# ---------------------------------------------------------------------------
# Descoberta de esquema
# ---------------------------------------------------------------------------

@dataclass
class Recurso:
    """Um recurso publicado pelo serviço OData."""

    nome: str
    parametros: tuple[str, ...]
    campos: tuple[str, ...]

    def __str__(self) -> str:
        par = ", ".join(self.parametros) or "-"
        return f"{self.nome}(params: {par}; {len(self.campos)} campos)"


class ClienteIFData:
    """Cliente HTTP com cache, repetição exponencial e descoberta de esquema."""

    def __init__(self, cfg: ConfigColeta | None = None, dir_cache: Path | None = None):
        self.cfg = cfg or CONFIG.coleta
        self.dir_cache = Path(dir_cache or DIR_BRUTOS)
        self.dir_cache.mkdir(parents=True, exist_ok=True)
        self.sessao = requests.Session()
        self.sessao.headers.update({"Accept": "application/json"})
        self._recursos: dict[str, Recurso] | None = None
        self.log: list[str] = []

    # -- infraestrutura ----------------------------------------------------

    def _anotar(self, msg: str) -> None:
        self.log.append(f"[{datetime.now():%H:%M:%S}] {msg}")

    def _caminho_cache(self, url: str, sufixo: str = ".json") -> Path:
        chave = hashlib.sha256(url.encode()).hexdigest()[:16]
        return self.dir_cache / f"ifdata_{chave}{sufixo}"

    def _get(self, url: str, *, texto: bool = False) -> Any:
        """GET com repetição exponencial. Erros 4xx não são repetidos."""
        cache = self._caminho_cache(url, ".txt" if texto else ".json")
        if self.cfg.usar_cache and cache.exists():
            self._anotar(f"cache: {cache.name}")
            bruto = cache.read_text(encoding="utf-8")
            return bruto if texto else json.loads(bruto)

        espera = self.cfg.espera_inicial_s
        ultimo_erro: Exception | None = None
        for tentativa in range(1, self.cfg.tentativas + 1):
            try:
                r = self.sessao.get(url, timeout=self.cfg.timeout_s)
                if 400 <= r.status_code < 500:
                    raise ErroColeta(
                        f"HTTP {r.status_code} em {url}\n"
                        f"Resposta: {r.text[:400]}\n"
                        "Erro de cliente: o recurso ou os parametros nao existem "
                        "como escritos. Rode ClienteIFData.descrever_servico()."
                    )
                r.raise_for_status()
                conteudo = r.text
                cache.write_text(conteudo, encoding="utf-8")
                self._anotar(f"OK  {r.status_code}  {len(conteudo):>9,} bytes  {url[:110]}")
                return conteudo if texto else json.loads(conteudo)
            except ErroColeta:
                raise
            except Exception as e:  # rede, timeout, 5xx, JSON malformado
                ultimo_erro = e
                self._anotar(f"tentativa {tentativa}/{self.cfg.tentativas} falhou: {type(e).__name__}: {e}")
                if tentativa < self.cfg.tentativas:
                    time.sleep(espera)
                    espera *= 2
        raise ErroColeta(f"Falha apos {self.cfg.tentativas} tentativas em {url}: {ultimo_erro}")

    # -- esquema -----------------------------------------------------------

    def metadados(self) -> dict[str, Recurso]:
        """Baixa e interpreta ``$metadata``; devolve os recursos publicados."""
        if self._recursos is not None:
            return self._recursos

        url = urllib.parse.urljoin(self.cfg.base_url, "$metadata")
        try:
            xml = self._get(url, texto=True)
        except Exception as e:
            diagnostico.registrar(
                area=AREA,
                item="Documento $metadata do servico IF.data nao pode ser lido.",
                impacto=(
                    "O pipeline nao consegue confirmar nomes de recursos, parametros e "
                    "colunas. Toda a coleta passa a depender de nomes presumidos."
                ),
                acao=(
                    "Executar o notebook em rede com saida para olinda.bcb.gov.br, ou "
                    "exportar os relatorios pela interface web do IF.data e usar "
                    "ifdata.carregar_csv_local(). Registrar no TCC qual caminho foi usado."
                ),
                severidade=diagnostico.Severidade.BLOQUEIA,
            )
            raise ErroColeta(f"Nao foi possivel obter o esquema do servico: {e}") from e

        self._recursos = _interpretar_metadata(xml)
        self._anotar(f"esquema: {len(self._recursos)} recurso(s) publicado(s)")
        return self._recursos

    def descrever_servico(self) -> pd.DataFrame:
        """Tabela legível do que o serviço realmente publica.

        Rodar isto **antes** de escrever qualquer consulta é a forma de evitar
        que o TCC dependa de um contrato de API imaginado.
        """
        rec = self.metadados()
        return pd.DataFrame(
            [
                {
                    "recurso": r.nome,
                    "parametros": ", ".join(r.parametros) or "(nenhum)",
                    "n_campos": len(r.campos),
                    "campos": ", ".join(r.campos[:14]) + (" ..." if len(r.campos) > 14 else ""),
                }
                for r in rec.values()
            ]
        ).sort_values("recurso", ignore_index=True)

    def resolver_recurso(self, *candidatos: str) -> str:
        """Devolve o primeiro candidato que existe no serviço."""
        rec = self.metadados()
        for c in candidatos:
            if c in rec:
                return c
        # tolerância a diferença de caixa/acento
        normalizados = {_normalizar(k): k for k in rec}
        for c in candidatos:
            if _normalizar(c) in normalizados:
                return normalizados[_normalizar(c)]
        raise ErroColeta(
            f"Nenhum dos recursos {candidatos} existe no servico. "
            f"Publicados: {sorted(rec)}"
        )

    # -- consultas ---------------------------------------------------------

    def consultar(self, recurso: str, parametros: dict[str, Any] | None = None,
                  opcoes: dict[str, str] | None = None) -> pd.DataFrame:
        """Consulta genérica a um recurso OData; devolve ``value`` como DataFrame.

        ``parametros`` são os parâmetros de função OData (sintaxe
        ``Recurso(P=@P)?@P=valor``); ``opcoes`` são opções de sistema
        (``$filter``, ``$select``, ``$top`` ...).
        """
        parametros = parametros or {}
        opcoes = {"$format": self.cfg.formato, **(opcoes or {})}

        if parametros:
            assinatura = ",".join(f"{k}=@{k}" for k in parametros)
            caminho = f"{recurso}({assinatura})"
        else:
            caminho = recurso

        consulta = {f"@{k}": _valor_odata(v) for k, v in parametros.items()}
        consulta.update(opcoes)
        url = (
            urllib.parse.urljoin(self.cfg.base_url, caminho)
            + "?"
            + urllib.parse.urlencode(consulta, safe="@$',()")
        )

        payload = self._get(url)
        registros = payload.get("value", payload) if isinstance(payload, dict) else payload
        df = pd.DataFrame(registros)
        df.attrs["url"] = url
        df.attrs["coletado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return df

    # -- conveniências de alto nível --------------------------------------

    def periodos_disponiveis(self) -> list[int]:
        """Períodos AAAAMM publicados, se o serviço expuser esse recurso."""
        try:
            nome = self.resolver_recurso("IfDataMesesDisponiveis", "MesesDisponiveis", "ListaDeMeses")
        except ErroColeta:
            diagnostico.registrar(
                area=AREA,
                item="Servico nao publica recurso de calendario (meses disponiveis).",
                impacto="O recorte 2019-2024 nao pode ser confirmado contra a fonte.",
                acao=(
                    "Confirmar manualmente no IF.data quais trimestres existem para S2/S3 "
                    "e ajustar config.ANOS. Documentar trimestres ausentes no TCC."
                ),
                severidade=diagnostico.Severidade.OBSERVA,
            )
            return periodos()
        df = self.consultar(nome)
        col = _primeira_coluna(df, r"anomes|periodo|data|mes")
        if col is None:
            return periodos()
        return sorted(int(str(v)[:6]) for v in df[col].dropna().unique())

    def cadastro(self, anomes: int) -> pd.DataFrame:
        """Cadastro de instituições de um período."""
        nome = self.resolver_recurso("IfDataCadastro", "Cadastro")
        parametros = _parametros_do_recurso(self.metadados()[nome], {"AnoMes": anomes})
        df = self.consultar(nome, parametros)
        df["anomes"] = anomes
        return df

    def valores(self, anomes: int, relatorio: str | int, tipo_instituicao: int) -> pd.DataFrame:
        """Valores de um relatório do IF.data para um período e tipo."""
        nome = self.resolver_recurso("IfDataValores", "Valores")
        desejados = {
            "AnoMes": anomes,
            "Relatorio": str(relatorio),
            "TipoInstituicao": tipo_instituicao,
        }
        parametros = _parametros_do_recurso(self.metadados()[nome], desejados)
        df = self.consultar(nome, parametros)
        df["anomes"] = anomes
        df["relatorio"] = str(relatorio)
        df["tipo_instituicao"] = tipo_instituicao
        return df

    def coletar_painel(self, relatorios: Iterable[str | int], tipos: Iterable[int],
                       periodos_alvo: Iterable[int] | None = None) -> pd.DataFrame:
        """Varre (período x relatório x tipo) e empilha tudo em um DataFrame longo.

        Falhas isoladas não interrompem a varredura: são registradas e o
        período segue ausente no painel — o que o diagnóstico final reporta.
        """
        alvo = list(periodos_alvo or periodos())
        partes: list[pd.DataFrame] = []
        falhas: list[str] = []

        for p in alvo:
            for rel in relatorios:
                for tipo in tipos:
                    try:
                        df = self.valores(p, rel, tipo)
                        if not df.empty:
                            partes.append(df)
                    except Exception as e:
                        falhas.append(f"{p}/rel={rel}/tipo={tipo}: {type(e).__name__}")

        if falhas:
            diagnostico.registrar(
                area=AREA,
                item=f"{len(falhas)} combinacao(oes) periodo/relatorio/tipo nao retornaram dados.",
                impacto=(
                    "O painel fica desbalanceado. Instituicoes com trimestres faltantes "
                    "produzem variacoes trimestrais espurias nos indicadores de delta."
                ),
                acao=(
                    "Verificar no IF.data se a ausencia e real (instituicao nao existia / "
                    "nao reapresentou) ou falha de coleta. Primeiras ocorrencias: "
                    + "; ".join(falhas[:8])
                ),
                severidade=diagnostico.Severidade.COMPROMETE,
            )

        if not partes:
            raise ErroColeta(
                "Nenhum dado coletado. Verifique saida de rede para olinda.bcb.gov.br "
                "ou use ifdata.carregar_csv_local()."
            )

        painel = pd.concat(partes, ignore_index=True)
        painel.attrs["coletado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return painel


# ---------------------------------------------------------------------------
# Caminho alternativo: exportações manuais do IF.data
# ---------------------------------------------------------------------------

#: Marcadores de ausência usados pelo IF.data nas exportações CSV.
AUSENTES_IFDATA = ("NA", "NA%", "N/A", "-", "", " ")


def _para_numero(serie: pd.Series) -> pd.Series:
    """Converte o formato numérico do IF.data para float.

    O CSV do IF.data usa convenção brasileira e traz percentuais com sufixo:

        "1.516.147.949"  -> 1516147949.0     (ponto = separador de milhar)
        "19,26%"         -> 19.26            (virgula = decimal, % removido)
        "NA" / "NA%"     -> NaN

    Deixar o pandas inferir aqui é o erro mais caro do pipeline: a coluna vira
    texto, todo indicador que dependa dela vira ``NaN``, e nada avisa.
    """
    s = serie.astype(str).str.strip()
    s = s.where(~s.isin(AUSENTES_IFDATA))
    s = (s.str.replace("%", "", regex=False)
          .str.replace(".", "", regex=False)     # separador de milhar
          .str.replace(",", ".", regex=False))   # decimal
    return pd.to_numeric(s, errors="coerce")


def carregar_ifdata_csv(caminho: Path | str, anomes: int | None = None) -> pd.DataFrame:
    """Lê uma exportação CSV do IF.data respeitando o formato real do arquivo.

    Trata: BOM UTF-8, separador ``;``, ponto como separador de milhar, vírgula
    decimal, percentuais com ``%``, marcadores ``NA``/``NA%`` e a coluna vazia
    final produzida pelo ``;`` terminal.

    Devolve o quadro com ``cod_inst`` (a coluna "Código" do IF.data) e
    ``anomes``, e com as colunas de valor já convertidas para float.
    """
    caminho = Path(caminho)

    # ------------------------------------------------------------------
    # Cabeçalho hierárquico.
    #
    # As exportações do IF.data usam de uma a três linhas de cabeçalho: a
    # primeira traz os grupos sintéticos ("Operações de Crédito"), as demais
    # detalham as contas analíticas ("Provisão sobre Operações de Crédito").
    # Ler apenas a primeira linha perde as contas analíticas — que são
    # justamente as que sustentam os indicadores prudenciais — e ainda trata
    # as demais linhas de cabeçalho como se fossem instituições.
    #
    # A primeira linha de dados é identificada pelo código da instituição na
    # segunda coluna (inteiro de seis ou mais dígitos). O nome de cada coluna
    # é o rótulo do nível mais profundo preenchido.
    # ------------------------------------------------------------------
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        todas = list(csv.reader(fh, delimiter=";"))
    if not todas:
        raise ErroColeta(f"Arquivo vazio: {caminho}")

    i_dados = next(
        (i for i, l in enumerate(todas)
         if len(l) > 1 and re.fullmatch(r"\d{6,}", l[1].strip())),
        1,
    )
    cabecalho = todas[:i_dados]
    largura = max(len(l) for l in todas)

    nomes: list[str] = []
    for j in range(largura):
        niveis = [l[j].strip() for l in cabecalho if j < len(l) and l[j].strip()]
        nomes.append(niveis[-1] if niveis else "")

    corpo = [l + [""] * (largura - len(l)) for l in todas[i_dados:]]
    df = pd.DataFrame(corpo, columns=pd.Index(nomes, name=None), dtype=str)
    df.attrs["linhas_cabecalho"] = i_dados

    # A exportação termina com ';', gerando uma coluna final sem nome.
    df = df.loc[:, [c for c in df.columns if str(c).strip() != ""]]
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    # Identificador da instituição.
    col_codigo = _primeira_coluna(df, r"^codigo$|^codinst$|^cnpj$")
    if col_codigo:
        df = df.rename(columns={col_codigo: "cod_inst"})
        df["cod_inst"] = df["cod_inst"].astype(str).str.strip()
    else:
        diagnostico.registrar(
            area=AREA,
            item=f"Coluna de codigo da instituicao nao encontrada em {caminho.name}.",
            impacto="Sem identificador nao ha painel longitudinal: cada trimestre fica solto.",
            acao=(
                "Conferir o cabecalho do CSV e renomear a coluna de identificacao para "
                "'cod_inst'. Area: ifdata.carregar_ifdata_csv()."
            ),
            severidade=diagnostico.Severidade.BLOQUEIA,
        )

    # Período: da coluna "Data" (MM/AAAA) ou do nome do arquivo.
    col_data = _primeira_coluna(df, r"^data$|^database$|^anomes$")
    if anomes is not None:
        df["anomes"] = anomes
    elif col_data:
        d = df[col_data].astype(str).str.strip()
        extraido = d.str.extract(r"(\d{2})/(\d{4})")
        df["anomes"] = (extraido[1] + extraido[0]).astype("Int64")
    else:
        m = re.search(r"(20\d{2})[-_]?(0[369]|12)", caminho.stem)
        df["anomes"] = int(m.group(1) + m.group(2)) if m else pd.NA

    # ------------------------------------------------------------------
    # Separação entre instituições e o rodapé de legenda.
    #
    # A exportação do IF.data anexa, ao final do arquivo, um bloco com a
    # legenda dos códigos (TCB, SR, TD, TC) e os TOTAIS AGREGADOS de cada
    # categoria — por exemplo, "S2 - Segmento 2" com a soma do ativo de todo
    # o segmento. Essas linhas não têm código de instituição.
    #
    # Mantê-las faria agregados de trilhões entrarem no painel como se fossem
    # instituições, contaminando winsorização, z-score por pares e o próprio
    # treino da rede — sem produzir nenhum erro visível.
    # ------------------------------------------------------------------
    legenda = pd.DataFrame()
    if "cod_inst" in df.columns:
        sem_codigo = df["cod_inst"].isna() | (df["cod_inst"].astype(str).str.strip() == "")
        legenda = df.loc[sem_codigo].copy()
        df = df.loc[~sem_codigo].copy()
        if len(legenda):
            diagnostico.registrar(
                area=AREA,
                item=(
                    f"{len(legenda)} linha(s) de legenda/totais removidas de "
                    f"{caminho.name} (rodape da exportacao do IF.data)."
                ),
                impacto=(
                    "Se mantidas, os totais agregados por segmento e por tipo de "
                    "consolidado entrariam no painel como instituicoes."
                ),
                acao=(
                    "Nenhuma — remocao automatica. O bloco fica disponivel em "
                    "df.attrs['legenda'] e serve como dicionario de dados dos "
                    "codigos TCB, SR, TD e TC para o TCC."
                ),
                severidade=diagnostico.Severidade.OBSERVA,
            )

    # Colunas que permanecem texto; o resto é numérico.
    texto = {"cod_inst", "anomes"}
    for c in df.columns:
        if re.search(r"instituic|cidade|^uf$|^tcb$|^sr$|^td$|^tc$|^data$",
                     _normalizar(c)):
            texto.add(c)

    convertidas, falhas = [], []
    for c in df.columns:
        if c in texto:
            continue
        original_validos = df[c].astype(str).str.strip().isin(AUSENTES_IFDATA).eq(False).sum()
        df[c] = _para_numero(df[c])
        obtidos = int(df[c].notna().sum())
        convertidas.append(c)
        if original_validos and obtidos == 0:
            falhas.append(c)

    if falhas:
        diagnostico.registrar(
            area=AREA,
            item=f"Colunas que nao converteram para numero em {caminho.name}: {falhas}",
            impacto=(
                "Indicadores derivados dessas colunas ficam indefinidos. Como a conversao "
                "falha em silencio no pandas, sem esta verificacao o erro so apareceria "
                "como resultado vazio no fim do pipeline."
            ),
            acao=(
                "Inspecionar os valores brutos dessas colunas no CSV e ajustar "
                "ifdata._para_numero(). Area: ifdata.carregar_ifdata_csv()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )

    df.attrs["arquivo"] = caminho.name
    df.attrs["colunas_numericas"] = convertidas
    df.attrs["legenda"] = legenda
    return df.reset_index(drop=True)


def carregar_pasta_ifdata(diretorio: Path | str, padrao: str = "*.csv") -> pd.DataFrame:
    """Empilha todas as exportações CSV de uma pasta (um relatório do IF.data)."""
    diretorio = Path(diretorio)
    arquivos = sorted(diretorio.glob(padrao))
    if not arquivos:
        raise ErroColeta(f"Nenhum arquivo {padrao} em {diretorio}")

    partes, problemas = [], []
    for arq in arquivos:
        try:
            partes.append(carregar_ifdata_csv(arq))
        except Exception as e:
            problemas.append(f"{arq.name}: {type(e).__name__}: {e}")

    if problemas:
        diagnostico.registrar(
            area=AREA,
            item=f"{len(problemas)} arquivo(s) nao puderam ser lidos em {diretorio.name}.",
            impacto="Os trimestres correspondentes ficam ausentes do painel.",
            acao=f"Verificar: {'; '.join(problemas[:5])}. Area: ifdata.carregar_pasta_ifdata().",
            severidade=diagnostico.Severidade.COMPROMETE,
        )
    if not partes:
        raise ErroColeta(f"Nenhum arquivo legivel em {diretorio}")

    df = pd.concat(partes, ignore_index=True)
    df.attrs["n_arquivos"] = len(partes)
    df.attrs["relatorio"] = diretorio.name
    return df


def carregar_csv_local(diretorio: Path | str, padrao: str = "*.csv",
                       sep: str | None = None, decimal: str = ",") -> pd.DataFrame:
    """Empilha exportações CSV do IF.data salvas localmente.

    Usar quando não houver saída de rede (ambiente corporativo, proxy que
    bloqueia ``bcb.gov.br``) ou quando a banca exigir arquivo-fonte imutável
    anexado ao trabalho. O nome de cada arquivo deve conter o período no
    formato ``AAAAMM`` (ex.: ``ativos_202403.csv``).
    """
    diretorio = Path(diretorio)
    arquivos = sorted(diretorio.glob(padrao))
    if not arquivos:
        raise ErroColeta(f"Nenhum arquivo {padrao} em {diretorio}")

    partes = []
    sem_periodo = []
    for arq in arquivos:
        df = pd.read_csv(arq, sep=sep, decimal=decimal, engine="python", dtype=str)
        m = re.search(r"(20\d{4})", arq.stem)
        if m:
            df["anomes"] = int(m.group(1))
        else:
            sem_periodo.append(arq.name)
            df["anomes"] = pd.NA
        df["arquivo_origem"] = arq.name
        partes.append(df)

    if sem_periodo:
        diagnostico.registrar(
            area=AREA,
            item=f"{len(sem_periodo)} arquivo(s) sem periodo AAAAMM no nome.",
            impacto="Linhas sem periodo nao entram no painel longitudinal.",
            acao=f"Renomear incluindo AAAAMM: {', '.join(sem_periodo[:6])}",
            severidade=diagnostico.Severidade.COMPROMETE,
        )
    return pd.concat(partes, ignore_index=True)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def _interpretar_metadata(xml: str) -> dict[str, Recurso]:
    """Extrai EntitySets/FunctionImports e seus campos do ``$metadata`` (CSDL)."""
    raiz = ET.fromstring(xml)

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    tipos: dict[str, tuple[str, ...]] = {}
    for et in raiz.iter():
        if local(et.tag) in ("EntityType", "ComplexType"):
            nome = et.get("Name", "")
            campos = tuple(
                p.get("Name", "") for p in et if local(p.tag) == "Property"
            )
            tipos[nome] = campos

    recursos: dict[str, Recurso] = {}
    for et in raiz.iter():
        etiqueta = local(et.tag)
        if etiqueta not in ("EntitySet", "FunctionImport", "Function"):
            continue
        nome = et.get("Name", "")
        if not nome:
            continue
        tipo = (et.get("EntityType") or et.get("Type") or "").rsplit(".", 1)[-1]
        parametros = tuple(
            p.get("Name", "") for p in et
            if local(p.tag) == "Parameter" and p.get("Name")
        )
        recursos[nome] = Recurso(nome=nome, parametros=parametros, campos=tipos.get(tipo, ()))
    return recursos


def _parametros_do_recurso(recurso: Recurso, desejados: dict[str, Any]) -> dict[str, Any]:
    """Casa os parâmetros pedidos com os que o recurso declara.

    Evita o erro clássico de mandar ``TipoInstituicao`` para um recurso que
    espera ``TipoInstituicao1`` — ou de omitir um parâmetro obrigatório.
    """
    if not recurso.parametros:
        return {}
    mapa = {_normalizar(p): p for p in recurso.parametros}
    saida: dict[str, Any] = {}
    for chave, valor in desejados.items():
        real = mapa.get(_normalizar(chave))
        if real:
            saida[real] = valor
    faltando = [p for p in recurso.parametros if p not in saida]
    if faltando:
        diagnostico.registrar(
            area=AREA,
            item=f"Recurso {recurso.nome} exige parametros nao previstos: {faltando}",
            impacto="A consulta pode falhar ou retornar recorte diferente do pretendido.",
            acao=(
                f"Inspecionar ClienteIFData.descrever_servico() e informar valores para "
                f"{faltando} em ifdata.ClienteIFData.valores()."
            ),
            severidade=diagnostico.Severidade.COMPROMETE,
        )
    return saida


def _valor_odata(v: Any) -> str:
    """Formata valor para query OData (texto entre aspas simples)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return f"'{v}'"


def _normalizar(s: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _primeira_coluna(df: pd.DataFrame, padrao: str) -> str | None:
    for c in df.columns:
        if re.search(padrao, _normalizar(c)):
            return c
    return None
