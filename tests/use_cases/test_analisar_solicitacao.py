from types import SimpleNamespace

import pytest

from src.use_cases.documento_contratual.analisar_solicitacao import (
    AnalisarSolicitacaoAlteracaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


class FakeRepo:
    def __init__(self, solicitacao):
        self._solicitacao = solicitacao

    def get_by_id(self, _id):
        return self._solicitacao

    def marcar_analisada(self, solicitacao):
        solicitacao.status = "analisada"
        return solicitacao


def montar(solicitacao):
    uc = AnalisarSolicitacaoAlteracaoUseCase.__new__(AnalisarSolicitacaoAlteracaoUseCase)
    uc.solicitacoes = FakeRepo(solicitacao)
    return uc


def test_marca_analisada():
    solicitacao = SimpleNamespace(id=1, status="pendente")
    uc = montar(solicitacao)

    analisada = uc.execute(1)

    assert analisada.status == "analisada"


def test_recusa_ja_analisada():
    solicitacao = SimpleNamespace(id=1, status="analisada")
    uc = montar(solicitacao)

    with pytest.raises(RegraDeNegocioError, match="já foi analisada"):
        uc.execute(1)


def test_recusa_inexistente():
    uc = montar(None)

    with pytest.raises(RegraDeNegocioError, match="não encontrada"):
        uc.execute(1)
