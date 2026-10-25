"""Valida a extração manual de arquivos do IF.data antes de rodar o pipeline.

Baixar 24 trimestres à mão é trabalhoso e sujeito a lacunas silenciosas: um
arquivo esquecido, um trimestre baixado duas vezes com nomes diferentes, uma
exportação que mudou de separador. Qualquer um desses problemas só apareceria
lá na frente, disfarçado de resultado.

Este script confere, antes de qualquer modelagem:

    1. cobertura   — todos os trimestres do recorte estão presentes?
    2. duplicidade — algum período foi baixado mais de uma vez?
    3. formato     — separador, decimal e codificação são consistentes?
    4. colunas     — os rótulos batem entre os arquivos do mesmo relatório?
    5. conteúdo    — há linhas e valores numéricos utilizáveis?

Ao final, imprime a **união dos rótulos de coluna** encontrados. Essa lista é
o insumo direto do mapeamento contábil (seção 5 do notebook): é ela que diz
quais conceitos o IF.data realmente entrega.

Uso:

    cd "C:\\Documentos\\Projetos-Python\\TCC_S2S3"
    python testes\\validar_extracao_manual.py
    python testes\\validar_extracao_manual.py dados\\ifdata_bruto\\balanco
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

LARGURA = 78


def titulo(t: str) -> None:
    print("\n" + "=" * LARGURA)
    print(t)
    print("=" * LARGURA)


def periodos_esperados() -> list[int]:
    from fraude_s2s3.config import periodos

    return periodos()


def periodo_do_nome(nome: str) -> int | None:
    """Extrai AAAAMM do nome do arquivo. Aceita 202403, 2024-03 e 2024_03."""
    m = re.search(r"(20\d{2})[-_]?(0[369]|12)", nome)
    return int(m.group(1) + m.group(2)) if m else None


def detectar_formato(caminho: Path) -> dict:
    """Descobre separador, codificação e decimal por inspeção, sem adivinhar."""
    resultado = {"encoding": None, "sep": None, "decimal": None, "erro": None}

    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with caminho.open(encoding=enc) as f:
                amostra = f.read(8192)
            resultado["encoding"] = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if resultado["encoding"] is None:
        resultado["erro"] = "nao foi possivel decodificar o arquivo"
        return resultado

    try:
        resultado["sep"] = csv.Sniffer().sniff(amostra, delimiters=";,\t|").delimiter
    except csv.Error:
        contagem = {s: amostra.count(s) for s in (";", ",", "\t", "|")}
        resultado["sep"] = max(contagem, key=contagem.get) if max(contagem.values()) else ";"

    # Decimal: vírgula é o padrão brasileiro; detecta pelo padrão dígito,dígito
    if resultado["sep"] == ";":
        resultado["decimal"] = "," if re.search(r"\d,\d", amostra) else "."
    else:
        resultado["decimal"] = "."
    return resultado


def analisar(diretorio: Path) -> int:
    import pandas as pd

    titulo(f"1. ARQUIVOS ENCONTRADOS EM {diretorio}")
    if not diretorio.exists():
        print(f"  Diretorio nao existe: {diretorio}")
        print("  Crie-o e salve ali os CSV exportados do IF.data.")
        return 2

    arquivos = sorted(p for p in diretorio.rglob("*")
                      if p.suffix.lower() in (".csv", ".txt", ".tsv"))
    if not arquivos:
        print("  Nenhum arquivo .csv encontrado.")
        print("  Ver docs/GUIA_EXTRACAO_MANUAL.md, secao 3.")
        return 2

    print(f"  {len(arquivos)} arquivo(s).\n")
    for a in arquivos[:12]:
        print(f"    {a.relative_to(diretorio)}  ({a.stat().st_size:,} bytes)")
    if len(arquivos) > 12:
        print(f"    ... e mais {len(arquivos) - 12}")

    # ---------------------------------------------------------------- 2
    titulo("2. COBERTURA TEMPORAL")
    achados: dict[int, list[Path]] = defaultdict(list)
    sem_periodo: list[Path] = []
    for a in arquivos:
        p = periodo_do_nome(a.name)
        (achados[p].append(a) if p else sem_periodo.append(a))

    esperados = periodos_esperados()
    faltando = [p for p in esperados if p not in achados]
    extras = [p for p in sorted(achados) if p not in esperados]

    print(f"  Recorte do estudo : {esperados[0]} a {esperados[-1]} "
          f"({len(esperados)} trimestres)")
    print(f"  Trimestres cobertos: {len(esperados) - len(faltando)} de {len(esperados)}")

    if faltando:
        print(f"\n  AUSENTES ({len(faltando)}):")
        for i in range(0, len(faltando), 8):
            print("    " + "  ".join(str(x) for x in faltando[i:i + 8]))
        print("\n  Cada trimestre ausente quebra a serie: os indicadores de")
        print("  variacao interanual (delta_carteira, delta_roa, sgi_bancario)")
        print("  dependem do mesmo trimestre do ano anterior.")
    else:
        print("\n  Cobertura completa.")

    # -- cobertura por relatorio ------------------------------------------
    # Ter os 24 trimestres nao basta: cada um precisa dos seis relatorios.
    # Sem esta conferencia, faltar o 'passivo' em toda a base passaria por
    # "cobertura completa" e so apareceria como indicador ausente no fim.
    try:
        import sys as _s
        _s.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from fraude_s2s3.consolidacao import identificar_relatorio
    except Exception:
        identificar_relatorio = None

    if identificar_relatorio is not None:
        RELATORIOS = ("resumo", "ativo", "passivo", "dre", "info_cap", "segmentacao")
        grade: dict[int, set[str]] = defaultdict(set)
        nao_identificados: list[Path] = []
        for a in arquivos:
            per = periodo_do_nome(a.name)
            rel = identificar_relatorio(a.stem)
            if rel:
                if per:
                    grade[per].add(rel)
            else:
                nao_identificados.append(a)

        print(f"\n  Relatorios por trimestre (esperados {len(RELATORIOS)}):\n")
        cab = "    periodo  " + "  ".join(r[:8].rjust(8) for r in RELATORIOS)
        print(cab)
        print("    " + "-" * (len(cab) - 4))
        incompletos = 0
        for per in esperados:
            tem = grade.get(per, set())
            if not tem:
                continue
            marcas = "  ".join(("   ok   " if r in tem else "  FALTA ") for r in RELATORIOS)
            if len(tem) < len(RELATORIOS):
                incompletos += 1
            print(f"    {per}  {marcas}")

        total = sum(len(v) for v in grade.values())
        print(f"\n  Arquivos reconhecidos: {total} de "
              f"{len(esperados) * len(RELATORIOS)} esperados")
        if incompletos:
            print(f"  Trimestres incompletos: {incompletos}")
            print("\n  Cada relatorio ausente retira os conceitos que so ele traz:")
            print("    ativo       -> carteira de credito, provisao, TVM  (T1, T2, T3)")
            print("    passivo     -> depositos, captacao                 (concentracao)")
            print("    dre         -> resultado, margem, tributos         (T5, T6)")
            print("    info_cap    -> indice de Basileia, capital         (T4)")
            print("    segmentacao -> enquadramento S1-S5                 (recorte S2/S3)")
            print("    resumo      -> identificacao e conferencia")
        else:
            print("  Todos os trimestres presentes tem os seis relatorios.")

        if nao_identificados:
            print(f"\n  NOME NAO RECONHECIDO ({len(nao_identificados)}):")
            for a in nao_identificados[:8]:
                print(f"    {a.name}")
            print("\n  O relatorio e deduzido do nome. Mantenha a palavra-chave do")
            print("  IF.data no arquivo: Ativo, Passivo, Resumo, DRE/Resultado,")
            print("  Info de Cap, Segmentacao.")

    if extras:
        print(f"\n  Fora do recorte (serao ignorados): {extras}")
    if sem_periodo:
        print(f"\n  SEM PERIODO NO NOME ({len(sem_periodo)}):")
        for a in sem_periodo[:8]:
            print(f"    {a.name}")
        print("\n  Renomeie incluindo AAAAMM, ex.: 'ativo_202403.csv'.")
        print("  Sem isso o arquivo nao entra no painel longitudinal.")

    duplicados = {p: v for p, v in achados.items() if len(v) > 1}
    if duplicados:
        print(f"\n  PERIODOS COM MAIS DE UM ARQUIVO ({len(duplicados)}):")
        for p, v in list(duplicados.items())[:6]:
            print(f"    {p}: {[x.name for x in v]}")
        print("\n  Normal se forem relatorios diferentes (balanco, DRE, capital).")
        print("  Problema se for o mesmo relatorio baixado duas vezes.")

    # ---------------------------------------------------------------- 3
    titulo("3. FORMATO DOS ARQUIVOS")
    formatos = Counter()
    problemas = []
    for a in arquivos:
        f = detectar_formato(a)
        if f["erro"]:
            problemas.append((a.name, f["erro"]))
        else:
            formatos[(f["encoding"], f["sep"], f["decimal"])] += 1

    for (enc, sep, dec), n in formatos.most_common():
        visivel = {"\t": "TAB"}.get(sep, sep)
        print(f"  {n:>3} arquivo(s):  encoding={enc:<10} separador='{visivel}'  decimal='{dec}'")

    if len(formatos) > 1:
        print("\n  ATENCAO: formatos diferentes entre arquivos.")
        print("  Ao carregar, informe sep e decimal explicitamente em vez de")
        print("  deixar o pandas inferir — inferencia errada transforma numero")
        print("  em texto silenciosamente, e o indicador vira NaN sem aviso.")
    if problemas:
        print(f"\n  ILEGIVEIS: {problemas}")

    # ---------------------------------------------------------------- 4
    titulo("4. COLUNAS")
    colunas_por_arquivo: dict[str, list[str]] = {}
    todas: Counter = Counter()
    linhas_total = 0

    for a in arquivos:
        f = detectar_formato(a)
        if f["erro"]:
            continue
        try:
            df = pd.read_csv(a, sep=f["sep"], encoding=f["encoding"],
                             decimal=f["decimal"], dtype=str, engine="python",
                             on_bad_lines="skip")
        except Exception as e:
            print(f"  Falha ao ler {a.name}: {type(e).__name__}: {e}")
            continue
        colunas_por_arquivo[a.name] = list(df.columns)
        todas.update(df.columns)
        linhas_total += len(df)

    if not colunas_por_arquivo:
        print("  Nenhum arquivo pode ser lido.")
        return 2

    print(f"  Linhas somadas: {linhas_total:,}")
    print(f"  Rotulos distintos: {len(todas)}\n")

    universais = [c for c, n in todas.items() if n == len(colunas_por_arquivo)]
    parciais = [(c, n) for c, n in todas.most_common() if n < len(colunas_por_arquivo)]

    print(f"  Presentes em TODOS os arquivos ({len(universais)}):")
    for c in universais[:30]:
        print(f"    {c}")
    if len(universais) > 30:
        print(f"    ... e mais {len(universais) - 30}")

    if parciais:
        print(f"\n  Presentes em ALGUNS ({len(parciais)}) — normal se voce baixou")
        print("  relatorios diferentes; problema se for o mesmo relatorio:")
        for c, n in parciais[:20]:
            print(f"    [{n:>3}/{len(colunas_por_arquivo)}]  {c}")
        if len(parciais) > 20:
            print(f"    ... e mais {len(parciais) - 20}")

    # ---------------------------------------------------------------- 5
    titulo("5. CONFRONTO COM OS CONCEITOS EXIGIDOS PELO ESTUDO")
    from fraude_s2s3 import diagnostico, mapeamento

    diagnostico.limpar()
    mapa = mapeamento.resolver(list(todas))
    print(f"  Cobertura de conceitos: {mapa.cobertura:.0%}\n")

    for c in mapeamento.CONCEITOS:
        if c.chave in mapa.resolvidos:
            marca, detalhe = "[ok]   ", mapa.resolvidos[c.chave][:46]
        elif c.chave in mapa.ambiguos:
            marca, detalhe = "[?]    ", " | ".join(mapa.ambiguos[c.chave])[:46]
        else:
            marca = "[FALTA]" if c.obrigatorio else "[-]    "
            detalhe = "(obrigatorio)" if c.obrigatorio else "(opcional)"
        print(f"  {marca} {c.chave:<28} {detalhe}")

    obrig_faltando = [k for k in mapa.ausentes
                      if mapeamento.CONCEITOS_POR_CHAVE[k].obrigatorio]

    titulo("CONCLUSAO")
    if obrig_faltando:
        print(f"  Conceitos OBRIGATORIOS ausentes: {obrig_faltando}")
        print("\n  Baixe tambem os relatorios do IF.data que contem essas contas.")
        print("  Ver docs/GUIA_EXTRACAO_MANUAL.md, secao 2, para a correspondencia")
        print("  entre conceito e relatorio.")
        return 1
    if faltando:
        print("  Conceitos obrigatorios presentes, mas ha trimestres ausentes.")
        print("  O pipeline roda; a serie temporal fica incompleta e isso sera")
        print("  reportado como ponto de correcao na secao 16 do notebook.")
        return 1

    print("  Extracao completa e utilizavel.")
    print("  Proximo passo: notebook, secao 3.2 —")
    print('      bruto_longo = ifdata.carregar_csv_local(RAIZ / "dados" / "brutos")')
    return 0


def main() -> int:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "dados" / "brutos"
    print("=" * LARGURA)
    print("VALIDACAO DA EXTRACAO MANUAL DO IF.data".center(LARGURA))
    print("=" * LARGURA)
    return analisar(destino)


if __name__ == "__main__":
    raise SystemExit(main())
