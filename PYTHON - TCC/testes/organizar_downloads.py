"""Organiza os downloads manuais do IF.data.

Resolve o ponto mais penoso da extração manual: o navegador salva tudo como
``ifdata.csv``, ``ifdata (1).csv``, ``ifdata (2).csv``..., e renomear 96
arquivos à mão é onde o erro entra. Um trimestre trocado de posição produz
variação interanual falsa que nenhuma etapa posterior detecta.

A renomeação aqui usa a **ordem de download** (data de modificação do arquivo)
e a casa com a sequência cronológica de trimestres. Se você baixar em ordem,
o resultado é correto; e o script mostra o mapeamento **antes** de aplicar,
para você conferir.

Comandos
--------

    python testes\\organizar_downloads.py --criar-pastas
    python testes\\organizar_downloads.py --checklist
    python testes\\organizar_downloads.py --renomear dados\\brutos\\balanco --relatorio balanco
    python testes\\organizar_downloads.py --renomear dados\\brutos\\balanco --relatorio balanco --aplicar

Sem ``--aplicar`` nada é alterado: o script apenas mostra o que faria.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

LARGURA = 78

#: Relatórios sugeridos e os conceitos que cada um costuma trazer.
#: Os nomes na interface do IF.data devem ser confirmados na tela.
RELATORIOS = {
    "balanco": "Balanço Patrimonial (Ativo e Passivo)",
    "resultado": "Demonstração de Resultado",
    "carteira": "Carteira de crédito por nível de risco",
    "capital": "Informações de capital (Basileia)",
}


def periodos() -> list[int]:
    from fraude_s2s3.config import periodos as p

    return p()


def titulo(t: str) -> None:
    print("\n" + "=" * LARGURA)
    print(t)
    print("=" * LARGURA)


# ---------------------------------------------------------------------------

def criar_pastas() -> int:
    titulo("CRIANDO ESTRUTURA DE PASTAS")
    base = RAIZ / "dados" / "brutos"
    for nome, descricao in RELATORIOS.items():
        destino = base / nome
        destino.mkdir(parents=True, exist_ok=True)
        print(f"  {destino.relative_to(RAIZ)}   <- {descricao}")

    print("\n  Uma subpasta por relatorio. Isso permite conferir a cobertura")
    print("  de cada um separadamente e evita misturar arquivos de origens")
    print("  diferentes, que teriam colunas incompativeis.")
    return 0


def checklist() -> int:
    """Gera a lista de controle dos downloads."""
    ps = periodos()
    destino = RAIZ / "dados" / "brutos" / "CHECKLIST_DOWNLOADS.md"

    linhas = [
        "# Controle dos downloads do IF.data",
        "",
        "Marque cada arquivo conforme baixar. Preencha a data no rodapé —",
        "ela precisa constar no TCC (o IF.data republica períodos quando há",
        "reapresentação de documento).",
        "",
        "**Recorte escolhido:** ( ) conglomerado prudencial   ( ) instituição individual",
        "",
        "> Escolha um e mantenha em TODOS os downloads. Misturar os dois",
        "> duplica instituições e contamina a comparação entre segmentos.",
        "",
        "| # | Trimestre | " + " | ".join(RELATORIOS) + " |",
        "|---|---|" + "---|" * len(RELATORIOS),
    ]
    for i, p in enumerate(ps, 1):
        ano, mes = divmod(p, 100)
        linhas.append(f"| {i:02d} | {mes:02d}/{ano} | " + " | ".join("[ ]" for _ in RELATORIOS) + " |")

    linhas += [
        "",
        f"**Total:** {len(ps)} trimestres × {len(RELATORIOS)} relatórios = "
        f"**{len(ps) * len(RELATORIOS)} downloads**",
        "",
        "## Ordem recomendada",
        "",
        "Baixe **coluna por coluna**, não linha por linha: fixe o relatório e",
        "percorra os 24 trimestres mudando só a data-base. Alternar entre",
        "relatórios a cada trimestre é mais lento e erra mais.",
        "",
        "Ao terminar cada coluna, rode:",
        "",
        "```powershell",
        "python testes\\organizar_downloads.py --renomear dados\\brutos\\<relatorio> --relatorio <relatorio>",
        "```",
        "",
        "Confira o mapeamento na tela e repita com `--aplicar`.",
        "",
        "## Registro",
        "",
        "| Relatório | Nome exato na interface | Data do download | Trimestres obtidos |",
        "|---|---|---|---|",
    ] + [f"| {n} | | | /{len(ps)} |" for n in RELATORIOS] + [
        "",
        "**Ausências e motivo:**",
        "",
        "**Observações:**",
        "",
    ]

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas), encoding="utf-8")

    titulo("CHECKLIST GERADO")
    print(f"  {destino.relative_to(RAIZ)}")
    print(f"\n  {len(ps)} trimestres x {len(RELATORIOS)} relatorios = "
          f"{len(ps) * len(RELATORIOS)} downloads")
    print("\n  Sequencia dos trimestres:")
    for i in range(0, len(ps), 6):
        print("    " + "  ".join(str(x) for x in ps[i:i + 6]))
    return 0


def renomear(pasta: Path, relatorio: str, aplicar: bool,
             de: int | None, ate: int | None) -> int:
    titulo(f"RENOMEACAO — {pasta}")

    if not pasta.exists():
        print(f"  Pasta nao existe: {pasta}")
        print("  Rode antes:  python testes\\organizar_downloads.py --criar-pastas")
        return 2

    todos = sorted(
        (p for p in pasta.iterdir()
         if p.is_file() and p.suffix.lower() in (".csv", ".txt", ".tsv")),
        key=lambda p: p.stat().st_mtime,
    )
    if not todos:
        print("  Nenhum arquivo .csv na pasta.")
        return 2

    ja_nomeados = [p for p in todos if re.search(r"20\d{2}(0[369]|12)", p.stem)]
    pendentes = [p for p in todos if p not in ja_nomeados]

    print(f"  Arquivos na pasta      : {len(todos)}")
    print(f"  Ja com periodo no nome : {len(ja_nomeados)}")
    print(f"  A renomear             : {len(pendentes)}")

    if not pendentes:
        print("\n  Nada a fazer — todos os arquivos ja tem periodo no nome.")
        return 0

    alvo = [p for p in periodos()
            if (de is None or p >= de) and (ate is None or p <= ate)]
    ocupados = {int(re.search(r"20\d{2}(?:0[369]|12)", p.stem).group())
                for p in ja_nomeados}
    alvo = [p for p in alvo if p not in ocupados]

    print(f"  Trimestres disponiveis : {len(alvo)}")
    if de or ate:
        print(f"  Faixa                  : {de or 'inicio'} a {ate or 'fim'}")

    if len(pendentes) != len(alvo):
        print(f"\n  ATENCAO: {len(pendentes)} arquivo(s) para {len(alvo)} trimestre(s).")
        print("\n  Isso significa que a contagem nao bate. Causas comuns:")
        print("    - faltou baixar algum trimestre")
        print("    - baixou o mesmo trimestre duas vezes")
        print("    - ha arquivo de outro relatorio na pasta")
        print("\n  Corrija antes de aplicar. Se a intencao e renomear apenas")
        print("  parte, use --de e --ate para delimitar a faixa. Exemplo:")
        print("      --de 201903 --ate 201912   (os 4 trimestres de 2019)")
        if len(pendentes) > len(alvo):
            print("\n  Renomeacao NAO sera aplicada: ha mais arquivos que trimestres,")
            print("  e adivinhar qual sobra e o tipo de erro que contamina o painel.")
            return 1

    titulo("MAPEAMENTO PROPOSTO (por ordem de download)")
    print(f"  {'#':>3}  {'arquivo atual':<34} ->  {'novo nome':<26}")
    print("  " + "-" * (LARGURA - 4))

    plano: list[tuple[Path, Path]] = []
    for i, (origem, p) in enumerate(zip(pendentes, alvo), 1):
        novo = pasta / f"{relatorio}_{p}{origem.suffix.lower()}"
        conflito = novo.exists()
        marca = "  <- JA EXISTE" if conflito else ""
        print(f"  {i:>3}  {origem.name[:34]:<34} ->  {novo.name:<26}{marca}")
        if conflito:
            print("\n  Abortado: renomear sobrescreveria um arquivo existente.")
            return 1
        plano.append((origem, novo))

    print("\n  A ordem acima vem da DATA DE MODIFICACAO dos arquivos, ou seja,")
    print("  da ordem em que voce baixou. Confira se corresponde a sequencia")
    print("  cronologica que voce seguiu na interface do IF.data.")

    if not aplicar:
        titulo("SIMULACAO — NADA FOI ALTERADO")
        print("  Se o mapeamento acima estiver correto, repita com --aplicar:")
        print(f"\n    python testes\\organizar_downloads.py --renomear {pasta} "
              f"--relatorio {relatorio} --aplicar")
        return 0

    for origem, novo in plano:
        origem.rename(novo)
    titulo(f"{len(plano)} ARQUIVO(S) RENOMEADO(S)")
    print("  Proximo passo — validar a extracao:")
    print(f"\n    python testes\\validar_extracao_manual.py {pasta}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Organiza os downloads manuais do IF.data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--criar-pastas", action="store_true",
                    help="cria dados/brutos/<relatorio> para cada relatorio")
    ap.add_argument("--checklist", action="store_true",
                    help="gera a lista de controle dos downloads")
    ap.add_argument("--renomear", metavar="PASTA",
                    help="renomeia os arquivos da pasta pela ordem de download")
    ap.add_argument("--relatorio", metavar="NOME",
                    help="prefixo do novo nome (ex.: balanco)")
    ap.add_argument("--aplicar", action="store_true",
                    help="executa de fato; sem isso apenas simula")
    ap.add_argument("--de", type=int, metavar="AAAAMM",
                    help="primeiro trimestre da faixa")
    ap.add_argument("--ate", type=int, metavar="AAAAMM",
                    help="ultimo trimestre da faixa")
    args = ap.parse_args()

    if args.criar_pastas:
        return criar_pastas()
    if args.checklist:
        return checklist()
    if args.renomear:
        if not args.relatorio:
            print("Informe --relatorio (ex.: --relatorio balanco)")
            return 2
        return renomear(Path(args.renomear), args.relatorio,
                        args.aplicar, args.de, args.ate)

    ap.print_help()
    print("\nSequencia tipica de uso:")
    print("  1. --criar-pastas")
    print("  2. --checklist")
    print("  3. baixar os 24 trimestres de um relatorio")
    print("  4. --renomear <pasta> --relatorio <nome>          (simula)")
    print("  5. --renomear <pasta> --relatorio <nome> --aplicar")
    print("  6. validar_extracao_manual.py <pasta>")
    print("  7. repetir 3-6 para o proximo relatorio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
