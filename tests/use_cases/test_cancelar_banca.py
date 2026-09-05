"""§8, 2026-09-04 — `CancelarBancaUseCase`: a única saída manual que resta.

Sem o botão "Registrar realização", `data_hora` passar sozinho já marca a
banca como realizada e dispara as duas avaliações (ver
`finalizacao_automatica.py`). Cancelar é o jeito de tirar uma banca desse
trilho ANTES de ela acontecer — depois de `realizado_em`, não há mais o que
desfazer.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca.marcar_banca_escopo import CancelarBancaUseCase
from src.utils.exceptions import RegraDeNegocioError


class FakeBancaRepository:
    def __init__(self, db):
        pass

    def get_by_id(self, banca_id):
        return BANCAS.get(banca_id)

    def update(self, banca_id, **campos):
        banca = BANCAS[banca_id]
        for k, v in campos.items():
            setattr(banca, k, v)
        return banca


BANCAS = {}


@pytest.fixture(autouse=True)
def _bancas(monkeypatch):
    BANCAS.clear()
    monkeypatch.setattr(
        "src.use_cases.banca.marcar_banca_escopo.BancaRepository", FakeBancaRepository
    )
    yield BANCAS


def _banca(id=1, realizado_em=None, cancelada_em=None):
    b = SimpleNamespace(id=id, data_hora=datetime(2026, 9, 20, 14, 0),
                         realizado_em=realizado_em, cancelada_em=cancelada_em)
    BANCAS[id] = b
    return b


def test_cancela_uma_banca_ainda_nao_realizada(_bancas):
    _banca()

    resultado = CancelarBancaUseCase(db=None).execute(1)

    assert resultado["id"] == 1
    assert BANCAS[1].cancelada_em is not None


def test_banca_inexistente_devolve_none(_bancas):
    assert CancelarBancaUseCase(db=None).execute(999) is None


def test_banca_ja_realizada_nao_pode_ser_cancelada(_bancas):
    """A banca já aconteceu — cancelar não desfaz nada, e fingir que desfaz
    é pior que recusar."""
    _banca(realizado_em=datetime(2026, 9, 20, 14, 0))

    with pytest.raises(RegraDeNegocioError, match="já foi realizada"):
        CancelarBancaUseCase(db=None).execute(1)


def test_cancelar_de_novo_e_idempotente(_bancas):
    """Clicar duas vezes (duplo-clique, aba duplicada) não deve estourar nem
    trocar o horário do cancelamento."""
    primeiro_cancelamento = datetime(2026, 9, 18, 9, 0)
    _banca(cancelada_em=primeiro_cancelamento)

    resultado = CancelarBancaUseCase(db=None).execute(1)

    assert resultado["cancelada_em"] == primeiro_cancelamento
