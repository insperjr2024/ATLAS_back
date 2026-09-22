from types import SimpleNamespace

import pytest

from src.use_cases.documento_contratual.deletar_documento import (
    DeletarDocumentoContratualUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


class FakeRepo:
    def __init__(self, documento):
        self._documento = documento
        self.deletados = []

    def get_by_id(self, _id):
        return self._documento

    def delete(self, documento_id):
        self.deletados.append(documento_id)
        return True


def montar(documento):
    uc = DeletarDocumentoContratualUseCase.__new__(DeletarDocumentoContratualUseCase)
    uc.documentos = FakeRepo(documento)
    return uc


def test_apaga_documento_nao_confirmado():
    doc = SimpleNamespace(id=1, status="aguardando_preenchimento", confirmado=False)
    uc = montar(doc)

    uc.execute(1)

    assert uc.documentos.deletados == [1]


def test_recusa_documento_confirmado():
    doc = SimpleNamespace(id=1, status="aguardando_preenchimento", confirmado=True)
    uc = montar(doc)

    with pytest.raises(RegraDeNegocioError, match="não confirmado"):
        uc.execute(1)


def test_recusa_fora_de_aguardando_preenchimento():
    doc = SimpleNamespace(id=1, status="em_revisao_interna", confirmado=False)
    uc = montar(doc)

    with pytest.raises(RegraDeNegocioError, match="não confirmado"):
        uc.execute(1)


def test_recusa_inexistente():
    uc = montar(None)

    with pytest.raises(RegraDeNegocioError, match="não encontrado"):
        uc.execute(1)
