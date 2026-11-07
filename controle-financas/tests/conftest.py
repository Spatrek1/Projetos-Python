import pytest

from financas.db import Banco


@pytest.fixture
def banco():
    b = Banco(":memory:")
    yield b
    b.fechar()
