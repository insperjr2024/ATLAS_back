"""Leitura pública da tela de aprovação (§ Contratos, 2026-09-18)."""

from types import SimpleNamespace

import pytest

from src.use_cases.documento_contratual.get_aprovacao_por_token import (
    GetAprovacaoPorTokenUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


class FakeRepo:
    def __init__(self, registro=None):
        self._registro = registro

    def get_by_token(self, _token):
        return self._registro

    def get_by_id(self, _id):
        return self._registro


def montar(token, documento, versao):
    uc = GetAprovacaoPorTokenUseCase.__new__(GetAprovacaoPorTokenUseCase)
    uc.tokens = FakeRepo(token)
    uc.documentos = FakeRepo(documento)
    uc.versoes = FakeRepo(versao)
    return uc


def test_devolve_so_o_que_a_tela_publica_precisa():
    projeto = SimpleNamespace(nome="Projeto Alfa")
    documento = SimpleNamespace(tipo="contrato", status="aguardando_aprovacao_cliente", projeto=projeto)
    versao = SimpleNamespace(pdf_path="/gerados/x.pdf")
    tok = SimpleNamespace(usado=False, documento_id=1, versao_id=9)
    uc = montar(tok, documento, versao)

    resultado = uc.execute("qualquer-token")

    assert resultado == {
        "usado": False,
        "nome_projeto": "Projeto Alfa",
        "tipo_documento": "contrato",
        "status": "aguardando_aprovacao_cliente",
        "pdf_path": "/gerados/x.pdf",
    }


def test_recusa_token_inexistente():
    uc = montar(None, None, None)

    with pytest.raises(RegraDeNegocioError, match="Link inválido"):
        uc.execute("x")
