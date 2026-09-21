"""Aprovar internamente o rascunho, antes de liberar o envio ao cliente
(§ Contratos, 2026-09-21).

Mesmo padrão dos vizinhos: `__new__` + repositório fake, notificação
trocada por no-op.
"""

from types import SimpleNamespace

import pytest

import src.use_cases.documento_contratual.aprovar_internamente as aprovar_internamente_mod
from src.use_cases.documento_contratual.aprovar_internamente import (
    AprovarInternamenteDocumentoContratualUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


class FakeDocumentoRepo:
    def __init__(self, documento):
        self._documento = documento

    def get_by_id(self, _id):
        return self._documento

    def update(self, _id, **kwargs):
        for chave, valor in kwargs.items():
            setattr(self._documento, chave, valor)
        return self._documento


def documento(status="em_revisao_interna"):
    return SimpleNamespace(id=1, status=status, tipo="contrato", projeto_id=7)


def montar(doc, monkeypatch):
    monkeypatch.setattr(aprovar_internamente_mod, "documento_aprovado_internamente", lambda *a, **k: None)
    uc = AprovarInternamenteDocumentoContratualUseCase.__new__(
        AprovarInternamenteDocumentoContratualUseCase
    )
    uc.db = None
    uc.documentos = FakeDocumentoRepo(doc)
    return uc


class TestExecute:
    def test_aprova_um_documento_em_revisao_interna(self, monkeypatch):
        doc = documento()
        uc = montar(doc, monkeypatch)

        aprovado = uc.execute(1)

        assert aprovado.status == "aprovado_internamente"

    def test_recusa_fora_de_em_revisao_interna(self, monkeypatch):
        doc = documento(status="aguardando_preenchimento")
        uc = montar(doc, monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="aguardando_preenchimento"):
            uc.execute(1)

    def test_recusa_aprovar_duas_vezes(self, monkeypatch):
        doc = documento(status="aprovado_internamente")
        uc = montar(doc, monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="aprovado_internamente"):
            uc.execute(1)

    def test_recusa_documento_inexistente(self, monkeypatch):
        uc = montar(None, monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="não encontrado"):
            uc.execute(1)
