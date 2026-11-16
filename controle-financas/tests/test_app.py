"""Testes do app Android: dados das telas e configuração (sem celular)."""
from datetime import date

import pytest

from financas.fake_provider import FakeProvider
from financas.sync import sincronizar
from financasapp import configuracao, dados


def test_ultimos_meses_e_rotulos():
    assert dados.ultimos_meses(date(2026, 2, 10), 4) == ["2026-02", "2026-01", "2025-12",
                                                         "2025-11"]
    assert dados.rotulo_mes("2026-11") == "nov/2026"
    assert dados.data_curta("2026-10-15") == "15/10"


def test_separar_ids_aceita_virgula_linha_e_link():
    texto = "aaa, bbb\nccc  https://meu.pluggy.ai/connections/ddd/\naaa"
    assert configuracao.separar_ids(texto) == ["aaa", "bbb", "ccc", "ddd"]


def test_config_salva_e_carrega(tmp_path):
    caminho = tmp_path / "sub" / "config.json"
    assert configuracao.carregar(caminho).completa is False  # ainda não existe
    cfg = configuracao.ConfigApp("id", "segredo", ["i1", "i2"])
    configuracao.salvar(caminho, cfg)
    lido = configuracao.carregar(caminho)
    assert lido == cfg and lido.completa
    caminho.write_text("{quebrado", encoding="utf-8")
    assert configuracao.carregar(caminho) == configuracao.ConfigApp()


def test_telas_com_dados(banco):
    sincronizar(banco, FakeProvider(), desde=date(2026, 10, 1), ate=date(2026, 10, 31))
    r = dados.tela_resumo(banco, "2026-10")
    assert not r["sem_dados"] and r["receitas"] == "R$ 7.500,00"
    assert abs(sum(c["pct"] for c in r["categorias"]) - 100) < 0.01
    g = dados.tela_gastos(banco, "2026-10")
    assert g["quantidade"] == len(g["itens"]) > 0 and "Alimentação" in g["categorias"]
    so_mercado = dados.tela_gastos(banco, "2026-10", "Mercado")
    assert {i["categoria"] for i in so_mercado["itens"]} == {"Mercado"}
    i = dados.tela_investimentos(banco)
    assert {gr["nome"] for gr in i["grupos"]} == {"Renda fixa", "Fundos", "Ações"}
    p = dados.tela_patrimonio(banco)
    assert p["lista_contas"] and p["ultima_sync"]


def test_tela_vazia(banco):
    assert dados.tela_resumo(banco, "2026-10")["sem_dados"]
    assert dados.tela_investimentos(banco)["grupos"] == []


def test_regras_pelo_app(banco):
    sincronizar(banco, FakeProvider(), desde=date(2026, 10, 1), ate=date(2026, 10, 31))
    n = dados.adicionar_regra(banco, "netflix", "Streaming")
    assert n > 0
    regra = dados.listar_regras(banco)[0]
    assert (regra["padrao"], regra["categoria"]) == ("netflix", "Streaming")
    with pytest.raises(ValueError):
        dados.adicionar_regra(banco, " ", "X")
    assert dados.remover_regra(banco, regra["id"]) == n


def test_sincronizar_em_thread_usa_arquivo_proprio(tmp_path):
    db = str(tmp_path / "app.db")
    msg = dados.sincronizar_pluggy(db, "", "", [], dias_iniciais=10, provedor=FakeProvider())
    assert msg.startswith("Sincronizado: 2 conta(s)")


def test_app_monta_todas_as_telas(tmp_path, monkeypatch):
    """Sobe o app inteiro com o backend 'dummy' do Toga (sem janela de verdade)."""
    pytest.importorskip("toga_dummy")
    monkeypatch.setenv("TOGA_BACKEND", "toga_dummy")
    monkeypatch.setenv("FINANCAS_APP_DIR", str(tmp_path))
    dados.sincronizar_pluggy(str(tmp_path / "financas.db"), "", "", [], dias_iniciais=60,
                             provedor=FakeProvider())
    from financasapp.app import FinancasApp
    app = FinancasApp(formal_name="Finanças", app_id="br.controlefinancas.financasapp")
    for nome, area in app.areas.items():
        assert area.content is not None, nome
    # filtros, regras e configuração pela interface
    app.sel_cat_gastos.value = app.sel_cat_gastos.items[-1].value
    app.in_regra_padrao.value = "uber"
    app.in_regra_categoria.value = "Transporte App"
    app.adicionar_regra(None)
    assert "Regra salva" in app.status_ajustes.text
    app.in_client_id.value, app.in_client_secret.value = "id", "segredo"
    app.in_item_ids.value = "x1, x2"
    app.salvar_config(None)
    assert configuracao.carregar(tmp_path / "config.json").item_ids == ["x1", "x2"]
