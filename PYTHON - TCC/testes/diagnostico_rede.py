"""Diagnóstico de acesso ao IF.data (Banco Central do Brasil).

Executa uma bateria de verificações em ordem crescente de profundidade e, para
cada falha, imprime a causa provável e o passo seguinte. A ideia é distinguir
as situações que costumam ser confundidas entre si:

    * não há internet;
    * há internet, mas o DNS não resolve o host;
    * o host resolve, mas um proxy corporativo intercepta;
    * o proxy deixa passar, mas o certificado TLS é substituído (MITM);
    * tudo funciona e o problema era outro.

Uso:

    cd "C:\\Documentos\\Projetos-Python\\PYTHON - TCC"
    python testes\\diagnostico_rede.py
"""

from __future__ import annotations

import os
import socket
import ssl
import sys
import urllib.parse
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

LARGURA = 78


def titulo(texto: str) -> None:
    print("\n" + "=" * LARGURA)
    print(texto)
    print("=" * LARGURA)


def item(rotulo: str, valor) -> None:
    print(f"  {rotulo:<34} {valor}")


def bloco(rotulo: str, linhas: list[str]) -> None:
    print(f"\n  >>> {rotulo}")
    for l in linhas:
        print(f"      {l}")


# ---------------------------------------------------------------------------

def etapa_ambiente() -> None:
    titulo("1. AMBIENTE")
    item("Python", sys.version.split()[0])
    item("Executavel", sys.executable)
    item("Diretorio de trabalho", os.getcwd())

    for modulo in ("requests", "pandas", "numpy", "torch", "sklearn"):
        try:
            m = __import__(modulo)
            item(f"{modulo}", getattr(m, "__version__", "instalado"))
        except ImportError:
            item(f"{modulo}", "AUSENTE  -> pip install -r requirements.txt")


def etapa_proxy() -> tuple[str | None, str | None]:
    titulo("2. VARIAVEIS DE PROXY")
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy")

    item("HTTP_PROXY", http_proxy or "(nao definido)")
    item("HTTPS_PROXY", https_proxy or "(nao definido)")
    item("NO_PROXY", no_proxy or "(nao definido)")

    if not https_proxy:
        print("\n  Nenhum proxy configurado no ambiente. Se voce estiver em rede")
        print("  corporativa ou VPN, o proxy pode estar sendo aplicado de forma")
        print("  transparente, sem aparecer aqui.")
    return http_proxy, https_proxy


def etapa_dns(host: str) -> bool:
    titulo(f"3. RESOLUCAO DE NOME — {host}")
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        enderecos = sorted({i[4][0] for i in infos})
        item("Resolveu para", ", ".join(enderecos))
        return True
    except socket.gaierror as e:
        item("FALHOU", f"{type(e).__name__}: {e}")
        bloco("Causa provavel e proximo passo", [
            "O DNS nao conseguiu traduzir o nome para um endereco IP.",
            "",
            "1) Teste conectividade geral:   ping google.com",
            "2) Se o ping funciona mas este host nao resolve, o bloqueio e",
            "   especifico (filtro de DNS corporativo ou antivirus).",
            "3) Fale com o suporte de TI, ou use outra rede (4G/celular).",
            "4) Alternativa sem rede: exportacao manual do IF.data — ver o",
            "   passo a passo no fim deste diagnostico.",
        ])
        return False


def etapa_tcp(host: str, porta: int = 443) -> bool:
    titulo(f"4. CONEXAO TCP — {host}:{porta}")
    try:
        with socket.create_connection((host, porta), timeout=15):
            item("Conexao TCP", "estabelecida")
            return True
    except Exception as e:
        item("FALHOU", f"{type(e).__name__}: {e}")
        bloco("Causa provavel e proximo passo", [
            "O nome resolve, mas a porta 443 esta inacessivel.",
            "Tipicamente firewall, VPN ou antivirus com inspecao de rede.",
            "",
            "1) Desative temporariamente a VPN e repita este diagnostico.",
            "2) Teste em outra rede (roteamento pelo celular resolve na maioria",
            "   dos casos de bloqueio corporativo).",
            "3) Se persistir, siga pela exportacao manual do IF.data.",
        ])
        return False


def etapa_tls(host: str, porta: int = 443) -> bool:
    titulo(f"5. CERTIFICADO TLS — {host}")
    try:
        contexto = ssl.create_default_context()
        with socket.create_connection((host, porta), timeout=15) as sock:
            with contexto.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
                emissor = dict(x[0] for x in cert.get("issuer", []))
                item("Emissor do certificado", emissor.get("organizationName", "(nao informado)"))
                item("Valido ate", cert.get("notAfter", "?"))
                item("Protocolo", tls.version())

                # Heuristica por lista de permissao, nao por lista de bloqueio:
                # qualquer emissor que nao seja uma autoridade certificadora
                # publica conhecida indica interceptacao. Listar "proxies
                # conhecidos" falharia justamente nos casos novos.
                nome = emissor.get("organizationName", "")
                cas_publicas = (
                    "digicert", "sectigo", "let's encrypt", "lets encrypt",
                    "globalsign", "godaddy", "amazon", "google trust",
                    "entrust", "identrust", "thawte", "verisign", "certisign",
                    "ico brasil", "icp-brasil", "microsoft", "baltimore",
                    "usertrust", "comodo", "geotrust", "rapidssl", "zerossl",
                    "buypass", "actalis", "quovadis", "starfield",
                )
                if nome and not any(ca in nome.lower() for ca in cas_publicas):
                    bloco("ATENCAO — interceptacao TLS detectada", [
                        f"O certificado foi emitido por '{nome}', que nao e uma",
                        "autoridade certificadora publica conhecida.",
                        "Isso indica um proxy corporativo que substitui certificados.",
                        "O Python vai recusar a conexao por falha de verificacao.",
                        "",
                        "Correcao (NUNCA desative a verificacao TLS):",
                        "  1) Peca ao TI o certificado raiz da empresa (arquivo .crt/.pem)",
                        "  2) Aponte o Python para ele, no PowerShell:",
                        '     $env:REQUESTS_CA_BUNDLE = "C:\\caminho\\para\\ca-empresa.pem"',
                        "  3) Rode este diagnostico de novo na MESMA janela do terminal",
                    ])
                return True
    except ssl.SSLCertVerificationError as e:
        item("FALHOU", f"verificacao de certificado: {e}")
        bloco("Causa provavel e proximo passo", [
            "Ha um intermediario substituindo o certificado (proxy corporativo,",
            "antivirus com inspecao HTTPS) ou o repositorio de CAs esta desatualizado.",
            "",
            "1) Atualize os certificados raiz:  pip install --upgrade certifi",
            "2) Se for proxy corporativo, obtenha o certificado raiz da empresa e:",
            '     $env:REQUESTS_CA_BUNDLE = "C:\\caminho\\ca-empresa.pem"',
            "3) Se for antivirus, desative a inspecao HTTPS apenas para teste.",
            "",
            "NAO use verify=False: alem de inseguro, mascara o problema real e",
            "compromete a rastreabilidade da coleta no TCC.",
        ])
        return False
    except Exception as e:
        item("FALHOU", f"{type(e).__name__}: {e}")
        return False


def etapa_http(url: str) -> bool:
    titulo("6. REQUISICAO HTTPS AO SERVICO")
    try:
        import requests
    except ImportError:
        item("requests", "AUSENTE")
        print("\n  Instale as dependencias:  pip install -r requirements.txt")
        return False

    item("URL", url[:70] + ("..." if len(url) > 70 else ""))
    try:
        r = requests.get(url, timeout=60)
        item("Codigo HTTP", r.status_code)
        item("Tamanho da resposta", f"{len(r.content):,} bytes")
        item("Content-Type", r.headers.get("Content-Type", "?"))

        if r.status_code == 200:
            print("\n  SUCESSO. O servico respondeu e a coleta pode ser executada.")
            return True

        if r.status_code in (403, 407):
            bloco("Bloqueio de politica (403/407)", [
                "Um proxy ou firewall recusou a requisicao por regra, nao por erro.",
                "",
                "1) Verifique se ha proxy exigindo autenticacao (407).",
                "2) Teste em outra rede.",
                "3) Se for politica da instituicao, use a exportacao manual.",
            ])
        elif r.status_code == 404:
            bloco("Recurso nao encontrado (404)", [
                "O host respondeu, mas o caminho nao existe. Isso sugere que a URL",
                "base do servico mudou.",
                "",
                "1) Abra o IF.data no navegador e confirme o endereco atual da API.",
                "2) Ajuste 'base_url' em src/fraude_s2s3/config.py (ConfigColeta).",
                "3) Este e exatamente o tipo de divergencia que a secao 2 do notebook",
                "   foi feita para revelar — nao presuma o contrato da API.",
            ])
        else:
            bloco("Resposta inesperada", [
                f"Codigo {r.status_code}. Primeiros caracteres do corpo:",
                r.text[:200].replace("\n", " "),
            ])
        return False

    except requests.exceptions.SSLError as e:
        item("FALHOU", f"TLS: {str(e)[:120]}")
        print("\n  Ver orientacao da etapa 5 (certificado).")
        return False
    except requests.exceptions.ProxyError as e:
        item("FALHOU", f"proxy: {str(e)[:120]}")
        bloco("Proximo passo", [
            "O proxy configurado recusou ou nao respondeu.",
            "Verifique HTTPS_PROXY (etapa 2) ou remova-o para testar direto:",
            '  $env:HTTPS_PROXY = ""',
        ])
        return False
    except requests.exceptions.Timeout:
        item("FALHOU", "tempo esgotado")
        bloco("Proximo passo", [
            "A conexao ficou pendurada — sintoma tipico de firewall que descarta",
            "pacotes em silencio, em vez de recusar.",
            "Teste em outra rede antes de qualquer outra coisa.",
        ])
        return False
    except Exception as e:
        item("FALHOU", f"{type(e).__name__}: {str(e)[:120]}")
        return False


def plano_b() -> None:
    titulo("CAMINHO ALTERNATIVO — EXPORTACAO MANUAL")
    print("""
  Se a API permanecer inacessivel, o trabalho NAO fica inviabilizado. O IF.data
  permite baixar os relatorios pela interface web, e o pipeline aceita esses
  arquivos sem nenhuma alteracao de codigo.

  1) Abra o IF.data no navegador (site do Banco Central).
  2) Selecione a data-base (trimestre) e o relatorio desejado.
  3) Baixe o CSV.
  4) Salve em  dados\\brutos\\  incluindo o periodo AAAAMM no nome:
         ativo_201903.csv,  ativo_201906.csv,  ...
  5) No notebook, na secao 3.2, troque a coleta por:

         bruto_longo = ifdata.carregar_csv_local(RAIZ / "dados" / "brutos")

  Sao 24 trimestres x quantidade de relatorios — trabalhoso, mas viavel, e tem
  uma vantagem para a banca: os arquivos-fonte ficam anexados ao trabalho, o que
  torna o resultado reproduzivel de forma independente da disponibilidade da API.
""")


def main() -> int:
    print("=" * LARGURA)
    print("DIAGNOSTICO DE ACESSO AO IF.data / BANCO CENTRAL DO BRASIL".center(LARGURA))
    print("=" * LARGURA)

    try:
        from fraude_s2s3.config import CONFIG
        base = CONFIG.coleta.base_url
    except Exception as e:
        print(f"\n  Nao foi possivel importar a configuracao do projeto: {e}")
        print("  Rode a partir da pasta 'PYTHON - TCC'.")
        return 1

    host = urllib.parse.urlparse(base).hostname or "olinda.bcb.gov.br"

    etapa_ambiente()
    etapa_proxy()

    ok = etapa_dns(host)
    if ok:
        ok = etapa_tcp(host)
    if ok:
        etapa_tls(host)
        ok = etapa_http(urllib.parse.urljoin(base, "$metadata"))

    titulo("CONCLUSAO")
    if ok:
        print("  Acesso ao servico confirmado.")
        print("  Proximo passo: abrir notebooks/00_pipeline_s2_s3.ipynb e executar a secao 2,")
        print("  que lista os relatorios e tipos de instituicao realmente publicados.")
    else:
        print("  Acesso NAO confirmado. Siga a orientacao da etapa que falhou acima.")
        plano_b()
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
