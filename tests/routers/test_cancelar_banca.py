"""`POST /bancas/{id}/cancelar` — a única ação manual que resta desde que o
botão "Registrar realização" saiu (2026-09-04). A checagem de quem pode
(gerente/diretoria via `require_gestao`) é feita pelo `Depends` do FastAPI,
fora da função — aqui só a função em si, como em
`test_detalhes_da_banca_acesso.py`.
"""

import pytest
from fastapi import HTTPException

from src.routers import bancas
from src.utils.exceptions import RegraDeNegocioError


class FakeCancelarBancaUseCase:
    def __init__(self, db):
        pass

    def execute(self, banca_id):
        if banca_id == 999:
            return None
        if banca_id == 500:
            raise RegraDeNegocioError("Esta banca já foi realizada — não há o que cancelar")
        return {"id": banca_id, "cancelada_em": "2026-09-04T10:00:00"}


def test_cancela_a_banca(monkeypatch):
    monkeypatch.setattr(bancas, "CancelarBancaUseCase", FakeCancelarBancaUseCase)

    resultado = bancas.cancelar_banca(1, _=None, db=None)

    assert resultado["id"] == 1


def test_banca_inexistente_leva_404(monkeypatch):
    monkeypatch.setattr(bancas, "CancelarBancaUseCase", FakeCancelarBancaUseCase)

    with pytest.raises(HTTPException) as erro:
        bancas.cancelar_banca(999, _=None, db=None)

    assert erro.value.status_code == 404


def test_banca_ja_realizada_vira_erro_de_regra(monkeypatch):
    monkeypatch.setattr(bancas, "CancelarBancaUseCase", FakeCancelarBancaUseCase)

    with pytest.raises(HTTPException) as erro:
        bancas.cancelar_banca(500, _=None, db=None)

    assert erro.value.status_code == 422
    assert "já foi realizada" in str(erro.value.detail)


def test_rota_de_realizar_nao_existe_mais():
    """⭐ Proteção contra regressão: o botão "Registrar realização" saiu de
    vez — se alguém trouxer a rota de volta, este teste denuncia."""
    assert not hasattr(bancas, "realizar_banca")
