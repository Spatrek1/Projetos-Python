"""Detecção de atipicidade contábil em instituições financeiras S2 e S3.

Pacote de apoio ao TCC "Auditorias em instituições financeiras dos segmentos
S2 e S3", com dados públicos do IF.data/COSIF (Banco Central do Brasil).

Aviso metodológico que atravessa todo o pacote
----------------------------------------------
Nenhuma função aqui detecta fraude. O que se mede é **atipicidade contábil**:
distância entre o comportamento observado de uma instituição e o padrão dos
seus pares e do seu próprio histórico. Fraude é qualificação jurídica; exige
prova, contraditório e decisão de autoridade competente. A confusão entre as
duas coisas é o erro mais grave que este tipo de trabalho pode cometer, e o
pacote foi escrito para tornar essa confusão difícil.

Importação preguiçosa
---------------------
Os submódulos são carregados sob demanda (PEP 562). Assim, uma dependência
ausente derruba apenas o módulo que precisa dela, e não o pacote inteiro:
sem ``torch``, por exemplo, ``indicadores`` e ``mapeamento`` continuam
utilizáveis. A mensagem de erro indica qual biblioteca instalar.
"""

from __future__ import annotations

import importlib

__version__ = "0.1.0"

_SUBMODULOS = (
    "avaliacao", "baselines", "benford", "config", "consolidacao",
    "diagnostico", "ifdata", "indicadores", "interpretacao", "mapeamento",
    "painel", "redes", "segmentacao", "testes_analiticos", "vazamento",
)

#: Bibliotecas de terceiros exigidas por cada submódulo, para produzir uma
#: mensagem útil em vez de um ``ModuleNotFoundError`` cru vindo de dentro.
_DEPENDENCIAS = {
    "avaliacao": ("pandas", "numpy", "scipy", "scikit-learn"),
    "baselines": ("pandas", "numpy", "scikit-learn"),
    "benford": ("pandas", "numpy"),
    "consolidacao": ("pandas", "numpy"),
    # requests so e exigido pelo cliente HTTP (ClienteIFData), nao pela
    # leitura de exportacoes manuais.
    "ifdata": ("pandas",),
    "indicadores": ("pandas", "numpy"),
    "interpretacao": ("pandas", "numpy"),
    "mapeamento": ("pandas",),
    "painel": ("pandas", "numpy"),
    "redes": ("numpy", "torch"),
    "segmentacao": ("pandas", "numpy"),
    "testes_analiticos": ("pandas", "numpy"),
    "vazamento": ("pandas", "numpy"),
}

__all__ = [*_SUBMODULOS, "__version__"]


def __getattr__(nome: str):
    """Carrega o submódulo na primeira vez que ele for pedido (PEP 562)."""
    if nome not in _SUBMODULOS:
        raise AttributeError(f"módulo 'fraude_s2s3' não possui atributo '{nome}'")

    try:
        modulo = importlib.import_module(f".{nome}", __name__)
    except ImportError as e:
        faltando = getattr(e, "name", None) or "?"
        pacotes = _DEPENDENCIAS.get(nome, ())
        raise ImportError(
            f"\n\n"
            f"  O módulo 'fraude_s2s3.{nome}' precisa de '{faltando}', que não está instalado.\n"
            f"\n"
            f"  Dependências deste módulo: {', '.join(pacotes) or '(não catalogadas)'}\n"
            f"\n"
            f"  Instale tudo de uma vez, a partir da pasta do projeto:\n"
            f"      pip install -r requirements.txt\n"
            f"\n"
            f"  Erro original: {e}\n"
        ) from e

    globals()[nome] = modulo
    return modulo


def __dir__() -> list[str]:
    return sorted([*_SUBMODULOS, "__version__"])


def verificar_ambiente() -> None:
    """Relata quais submódulos estão utilizáveis no ambiente atual.

    Útil como primeiro comando após instalar as dependências: mostra o que
    está pronto e o que falta, sem interromper na primeira ausência.
    """
    print("=" * 72)
    print("VERIFICACAO DE AMBIENTE — fraude_s2s3".center(72))
    print("=" * 72)

    faltantes: set[str] = set()
    for nome in _SUBMODULOS:
        try:
            importlib.import_module(f".{nome}", __name__)
            print(f"  [ok]     {nome}")
        except ImportError as e:
            dep = getattr(e, "name", None) or "?"
            faltantes.add(dep)
            print(f"  [FALTA]  {nome:<16} precisa de '{dep}'")

    print("=" * 72)
    if faltantes:
        print(f"  Bibliotecas ausentes: {', '.join(sorted(faltantes))}")
        print("  Correcao:  pip install -r requirements.txt")
    else:
        print("  Ambiente completo. Todos os modulos podem ser importados.")
    print("=" * 72)
