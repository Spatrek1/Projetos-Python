"""Teste de fumaça do pipeline completo.

Verifica que as peças se encaixam — não avalia desempenho. Executar com:

    python -m pytest testes/ -q
ou
    python testes/test_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "testes"))

from fixture_fumaca import eventos_artificiais, painel_artificial  # noqa: E402
from fraude_s2s3 import (avaliacao, baselines, benford, diagnostico,  # noqa: E402
                         indicadores, interpretacao, mapeamento, painel,
                         redes, testes_analiticos, vazamento)


def test_mapeamento_resolve_conceitos_principais():
    rotulos = ["Ativo Total", "Operações de Crédito", "Patrimônio Líquido",
               "Lucro Líquido", "Provisão sobre Operações de Crédito",
               "Resultado de Intermediação Financeira", "Índice de Basileia"]
    mapa = mapeamento.resolver(rotulos)
    for chave in ("ativo_total", "carteira_credito", "patrimonio_liquido",
                  "lucro_liquido", "provisao_pcld", "resultado_intermediacao"):
        assert chave in mapa.resolvidos, f"{chave} nao resolvido"
    assert 0 < mapa.cobertura <= 1


def test_indicadores_constroem_e_declaram_ausencias():
    bruto = painel_artificial(n_instituicoes=12)
    ind = indicadores.construir(bruto)
    assert {"cod_inst", "anomes"}.issubset(ind.columns)
    construidos = ind.attrs["indicadores_construidos"]
    assert "soft_assets" in construidos
    assert "cobertura_provisao" in construidos
    assert len(indicadores.catalogo_df()) == len(indicadores.CATALOGO)


def test_indicadores_sem_insumo_nao_inventam_zero():
    """Insumo ausente omite o indicador; nao vira zero nem NaN silencioso."""
    bruto = painel_artificial(n_instituicoes=6).drop(columns=["provisao_pcld"])
    ind = indicadores.construir(bruto)
    for chave in ("cobertura_provisao", "descasamento_provisao"):
        assert chave not in ind.columns, f"{chave} nao deveria existir sem provisao_pcld"
        assert chave in ind.attrs["indicadores_ausentes"]
    # os que nao dependem da provisao continuam presentes
    assert "levi_bancario" in ind.columns


def test_painel_particiona_no_tempo_sem_sobreposicao():
    ind = indicadores.construir(painel_artificial(n_instituicoes=20))
    pronto = painel.construir(ind)
    aud = vazamento.auditar_particao_temporal(pronto.dados, pronto.treino, pronto.teste)
    assert aud["sobreposicao_temporal"] is False
    assert pronto.treino.sum() > 0 and pronto.teste.sum() > 0


def test_escalador_ajusta_apenas_no_treino():
    ind = indicadores.construir(painel_artificial(n_instituicoes=20))
    pronto = painel.construir(ind)
    treinado = pronto.dados.loc[pronto.treino, pronto.escalador.colunas]
    assert abs(float(treinado.median().median())) < 0.6, "treino deveria ficar centrado"


def test_guarda_de_circularidade_remove_componentes_do_rotulo():
    guarda = vazamento.GuardaCircularidade(
        componentes_do_rotulo={"delta_roa", "soft_assets"}, nome_do_rotulo="teste"
    )
    atributos = ["delta_roa", "z_par_delta_roa", "faltante_soft_assets",
                 "levi_bancario", "z_par_levi_bancario"]
    limpos = guarda.filtrar(atributos)
    assert limpos == ["levi_bancario", "z_par_levi_bancario"]
    try:
        guarda.exigir_limpo(atributos)
        raise AssertionError("deveria ter levantado VazamentoDetectado")
    except vazamento.VazamentoDetectado:
        pass


def test_rede_treina_e_produz_escore_estavel():
    ind = indicadores.construir(painel_artificial(n_instituicoes=30))
    pronto = painel.construir(ind)
    cfg = redes.CONFIG.rede
    res = redes.treinar_autoencoder(
        pronto.matriz(pronto.treino),
        pronto.matriz(pronto.validacao),
        pronto.matriz(np.ones(len(pronto.dados), dtype=bool)),
        cfg=type(cfg)(**{**cfg.__dict__, "epocas": 30, "sementes": (0, 1)}),
    )
    assert len(res.escores) == len(pronto.dados)
    assert np.isfinite(res.escores).all()
    assert res.erro_por_atributo.shape == (len(pronto.dados), len(pronto.atributos))


def test_sequencias_e_gru():
    ind = indicadores.construir(painel_artificial(n_instituicoes=15))
    pronto = painel.construir(ind)
    X, y, idx = painel.sequencias(pronto, janela=4)
    assert X.ndim == 3 and X.shape[1] == 4
    assert len(idx) == len(X) == len(y)


def test_baselines_e_concordancia():
    ind = indicadores.construir(painel_artificial(n_instituicoes=25))
    pronto = painel.construir(ind)
    Xtr = pronto.matriz(pronto.treino)
    Xall = pronto.matriz(np.ones(len(pronto.dados), dtype=bool))
    tabela = baselines.painel_de_escores(Xtr, Xall, escore_rede=np.random.rand(len(Xall)))
    assert {"pca", "mahalanobis", "isolation_forest"}.issubset(tabela.columns)
    corr = baselines.concordancia(tabela)
    assert corr.shape[0] == corr.shape[1]


def test_avaliacao_por_eventos_e_metricas():
    bruto = painel_artificial(n_instituicoes=25)
    ind = indicadores.construir(bruto)
    pronto = painel.construir(ind)
    escores = pronto.dados[["cod_inst", "anomes"]].copy()
    escores["escore"] = np.random.default_rng(0).random(len(escores))
    eventos = eventos_artificiais(bruto)
    res = avaliacao.validar_por_eventos(escores, eventos)
    assert res.n_eventos == len(eventos)
    assert {"k", "precisao_em_k", "recall_em_k"}.issubset(res.tabela_k.columns)

    est = avaliacao.estabilidade_temporal(escores)
    assert "spearman" in est.columns


def test_rotulo_fraco_declara_componentes():
    ind = indicadores.construir(painel_artificial(n_instituicoes=20))
    y, comps = avaliacao.rotulo_fraco(ind, ["levi_bancario", "aqi_bancario"])
    assert set(comps).issubset({"levi_bancario", "aqi_bancario"})
    assert set(np.unique(y)).issubset({0, 1})


def test_benford_classifica_e_avisa():
    rng = np.random.default_rng(0)
    valores = 10 ** rng.uniform(2, 8, size=5000)      # escala livre -> conforme
    r = benford.testar(valores, posicao=1)
    assert r["n"] > 0 and np.isfinite(r["mad"])
    assert r["classificacao"] in {c[2] for c in benford.LIMIARES_MAD_D1}


def test_interpretacao_gera_narrativa_sem_afirmar_fraude():
    ind = indicadores.construir(painel_artificial(n_instituicoes=15))
    pronto = painel.construir(ind)
    erro = np.abs(np.random.default_rng(1).normal(size=(len(pronto.dados), len(pronto.atributos))))
    dec = interpretacao.decompor_erro(erro, pronto.atributos,
                                      pronto.dados[["cod_inst", "anomes"]].reset_index(drop=True))
    assert {"cod_inst", "anomes", "atributo", "participacao_no_erro"}.issubset(dec.columns)
    linha = dec.iloc[0]
    texto = interpretacao.narrativa(dec, linha["cod_inst"], linha["anomes"],
                                    indicadores.catalogo_df())
    assert "nao de indicio de irregularidade" in texto.lower().replace("ã", "a").replace("í", "i")


def test_diagnostico_produz_relatorio():
    diagnostico.limpar()
    ind = indicadores.construir(painel_artificial(n_instituicoes=10).drop(columns=["carteira_eh"]))
    painel.construir(ind)
    texto = diagnostico.relatorio()
    assert "PONTOS DE CORRECAO" in texto
    assert len(diagnostico.pendencias()) > 0
    assert isinstance(diagnostico.para_dataframe(), pd.DataFrame)


def _painel_para_testes():
    ind = indicadores.construir(painel_artificial(n_instituicoes=24))
    ind["segmento"] = np.where(ind["cod_inst"].astype(str).str[-1].astype(int) < 3, "S2", "S3")
    return ind


def test_testes_analiticos_cobrem_os_seis_parametros():
    ancoras = {t.parametro for t in testes_analiticos.CATALOGO}
    assert ancoras == {"provisao_pcld", "carteira_credito", "ativo_total",
                       "patrimonio_liquido", "resultado_intermediacao", "lucro_liquido"}
    quadro = testes_analiticos.catalogo_df()
    assert len(quadro) == 6
    assert quadro["procedimento_de_auditoria"].str.len().min() > 40


def test_sinalizacao_e_monotonica_no_limiar():
    """Limiar mais exigente nao pode sinalizar mais.

    Protege contra condicoes corroborantes com patamar fixo, que tornariam a
    taxa insensivel ao parametro e a analise de sensibilidade vazia.
    """
    ind = _painel_para_testes()
    sens = testes_analiticos.sensibilidade(ind, limiares=(2.0, 3.0, 4.0))
    for t in testes_analiticos.CATALOGO:
        serie = sens[t.codigo].dropna().tolist()
        assert serie == sorted(serie, reverse=True), f"{t.codigo} nao e monotonico: {serie}"


def test_t1_sinaliza_carteira_viva_sem_provisao():
    """Provisao exatamente zero e condicao categorica, nao cauda de distribuicao.

    Na escala simetrica em MAD a cobertura nula fica a cerca de 2 desvios da
    mediana e escaparia de qualquer limiar usual.
    """
    ind = _painel_para_testes()
    ind.loc[ind.index[:4], "cobertura_provisao"] = 0.0
    ind.loc[ind.index[:4], "peso_carteira"] = 0.5
    sinal = testes_analiticos.aplicar(ind)
    assert sinal.loc[sinal.index[:4], "T1_sinaliza"].all()


def test_escopo_de_materialidade_exclui_credito_imaterial():
    ind = _painel_para_testes()
    ind["cobertura_provisao"] = 0.0
    ind["peso_carteira"] = 0.01
    sinal = testes_analiticos.aplicar(ind)
    assert not sinal["T1_sinaliza"].any(), "T1 nao pode se aplicar a carteira imaterial"


def test_persistencia_separa_estrutural_de_episodico():
    ind = _painel_para_testes()
    sinal = testes_analiticos.aplicar(ind)
    marcas = [c for c in sinal.columns if c.endswith("_sinaliza")]
    sempre = sinal["cod_inst"].iloc[0]
    sinal.loc[sinal["cod_inst"] == sempre, marcas] = True
    pers = testes_analiticos.classificar_persistencia(sinal)
    assert (pers.loc[pers["cod_inst"] == sempre, "classe"] == "estrutural").all()
    foco = testes_analiticos.foco_de_exame(sinal)
    assert sempre not in set(foco["cod_inst"]), "sinalizacao estrutural deve sair do foco"


def test_saida_dos_testes_nao_afirma_irregularidade():
    ind = _painel_para_testes()
    sinal = testes_analiticos.aplicar(ind)
    alvo = sinal[sinal["n_testes_sinalizados"] > 0]
    if alvo.empty:
        return
    r = alvo.iloc[0]
    texto = testes_analiticos.detalhar(sinal, r["cod_inst"], r["anomes"]).lower()
    assert "nao indicio de irregularidade" in texto.replace("ã", "a").replace("í", "i")


if __name__ == "__main__":
    falhas = 0
    for nome, funcao in sorted(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            diagnostico.limpar()
            try:
                funcao()
                print(f"  ok    {nome}")
            except Exception as e:
                falhas += 1
                print(f"  FALHA {nome}: {type(e).__name__}: {e}")
    print(f"\n{falhas} falha(s).")
    sys.exit(1 if falhas else 0)
