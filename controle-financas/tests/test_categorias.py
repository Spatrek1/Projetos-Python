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


def test_categorias_especificas_vencem_as_genericas():
    # categorias reais vindas da Pluggy que antes caíam no lugar errado
    casos = {
        "Proceeds interests and dividends": "Rendimentos",   # não "Impostos e Taxas"
        "Interests charged": "Impostos e Taxas",
        "Fixed income": "Investimentos",                     # não "Receitas"
        "Income taxes": "Impostos e Taxas",                  # não "Receitas"
        "Credit card payment": "Pagamento de fatura",        # não "Outros"
        "Same person transfer": "Entre contas próprias",     # não "Transferências"
        "Transfer - Internal": "Entre contas próprias",
        "Transfer - PIX": "Transferências",
        "Taxi and ride-hailing": "Transporte",               # não "Impostos" (tax)
        "Digital services": "Assinaturas",                   # não "Serviços"
        "Services": "Serviços",
        "Vehicle insurance": "Seguros",
        "Pet supplies and vet": "Pets",
        "Cinema, theater and concerts": "Lazer",
    }
    for categoria_banco, esperado in casos.items():
        assert categorizar("X", categoria_banco, []) == esperado, categoria_banco
