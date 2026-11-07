from datetime import date

from financas.fake_provider import FakeProvider
from financas.relatorios import exportar_csv, resumo_mensal
from financas.sync import recategorizar, sincronizar


def test_sincronizacao_idempotente(banco):
    p = FakeProvider()
    r1 = sincronizar(banco, p, desde=date(2026, 10, 1), ate=date(2026, 10, 31))
    assert r1.novas > 0 and r1.contas == 2
    r2 = sincronizar(banco, p, desde=date(2026, 10, 1), ate=date(2026, 10, 31))
    assert r2.novas == 0 and r2.atualizadas == 0


def test_categoria_manual_sobrevive_a_sync_e_regras(banco):
    p = FakeProvider()
    sincronizar(banco, p, desde=date(2026, 10, 1), ate=date(2026, 10, 31))
    alvo = banco.buscar_transacoes(tipo="DEBITO", limite=1)[0]
    banco.definir_categoria_manual(alvo["id"], "Minha Categoria")
    banco.adicionar_regra(alvo["descricao"], "Regra")
    recategorizar(banco)
    sincronizar(banco, p, desde=date(2026, 10, 1), ate=date(2026, 10, 31))
    linha = banco.conn.execute("SELECT categoria FROM transacoes WHERE id=?",
                               (alvo["id"],)).fetchone()
    assert linha["categoria"] == "Minha Categoria"


def test_resumo_e_exportacao(banco, tmp_path):
    sincronizar(banco, FakeProvider(), desde=date(2026, 10, 1), ate=date(2026, 10, 31))
    r = resumo_mensal(banco, "2026-10")
    assert r.receitas == 750_000  # um salário no dia 5
    assert r.gastos == sum(r.por_categoria.values()) > 0
    n = exportar_csv(banco, tmp_path / "out.csv")
    assert n == len(banco.buscar_transacoes())


def test_sync_incremental_usa_ultima_data(banco):
    sincronizar(banco, FakeProvider(), desde=date(2026, 10, 1), ate=date(2026, 10, 31))
    r = sincronizar(banco, FakeProvider(), ate=date(2026, 11, 7))
    assert r.desde == date(2026, 10, 24)
