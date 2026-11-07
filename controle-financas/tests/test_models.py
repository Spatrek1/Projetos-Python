from financas.models import formatar_brl, para_centavos


def test_para_centavos():
    assert para_centavos(12.34) == 1234
    assert para_centavos(-0.1) == 10
    assert para_centavos("39.90") == 3990
    assert para_centavos(0.005) == 1


def test_formatar_brl():
    assert formatar_brl(123456789) == "R$ 1.234.567,89"
    assert formatar_brl(-505) == "-R$ 5,05"
    assert formatar_brl(0) == "R$ 0,00"
