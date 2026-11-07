from financas.categorias import OUTROS, categorizar


def test_regra_do_usuario_tem_prioridade():
    regras = [("ifood", "Delivery")]
    assert categorizar("IFOOD *RESTAURANTE", "Food delivery", regras) == "Delivery"


def test_regra_ignora_acentos_e_caixa():
    assert categorizar("PADARIA SÃO JOÃO", "", [("sao joao", "Padaria")]) == "Padaria"


def test_mapeia_categoria_do_banco():
    assert categorizar("POSTO SHELL", "Gas stations", []) == "Transporte"


def test_sem_informacao_vira_outros():
    assert categorizar("XPTO", "", []) == OUTROS
