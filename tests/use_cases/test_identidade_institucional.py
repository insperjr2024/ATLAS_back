from types import SimpleNamespace

import pytest

from src.use_cases.documento_contratual.identidade_institucional import (
    AtualizarIdentidadeInstitucionalUseCase,
    GetIdentidadeInstitucionalUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


class FakeRepo:
    def __init__(self, identidade):
        self._identidade = identidade

    def get(self):
        return self._identidade

    def update(self, **kwargs):
        if not self._identidade:
            return None
        for chave, valor in kwargs.items():
            setattr(self._identidade, chave, valor)
        return self._identidade


def identidade():
    return SimpleNamespace(presidente_nome="Fulano", testemunha1_nome="Pedro")


def test_get_devolve_a_linha_unica():
    uc = GetIdentidadeInstitucionalUseCase.__new__(GetIdentidadeInstitucionalUseCase)
    uc.identidade = FakeRepo(identidade())

    assert uc.execute().presidente_nome == "Fulano"


def test_atualiza_campos_conhecidos():
    uc = AtualizarIdentidadeInstitucionalUseCase.__new__(AtualizarIdentidadeInstitucionalUseCase)
    uc.identidade = FakeRepo(identidade())

    atualizado = uc.execute({"presidente_nome": "Novo Presidente"})

    assert atualizado.presidente_nome == "Novo Presidente"


def test_recusa_campo_desconhecido():
    uc = AtualizarIdentidadeInstitucionalUseCase.__new__(AtualizarIdentidadeInstitucionalUseCase)
    uc.identidade = FakeRepo(identidade())

    with pytest.raises(RegraDeNegocioError, match="Campo.*desconhecido"):
        uc.execute({"id": 99})


def test_recusa_sem_linha_cadastrada():
    uc = AtualizarIdentidadeInstitucionalUseCase.__new__(AtualizarIdentidadeInstitucionalUseCase)
    uc.identidade = FakeRepo(None)

    with pytest.raises(RegraDeNegocioError, match="não encontrada"):
        uc.execute({"presidente_nome": "X"})
