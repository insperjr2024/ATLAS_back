"""`HardDeletarDocumentoContratualUseCase` — apagar de vez, mesmo assinado e
arquivado, sem violar FK e sem nunca tocar no `projeto` (2026-09-24, a
pedido: a diretoria pediu uma saída pra contrato já arquivado, que a
exclusão simples — `deletar_documento.py` — recusa de propósito).
"""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from src.use_cases.documento_contratual.hard_deletar_documento import (
    HardDeletarDocumentoContratualUseCase,
)
from src.utils.exceptions import RegraDeNegocioError, ResourceInUseError

DOCUMENTOS = {}
VERSOES_POR_DOCUMENTO = {}
SOLICITACOES_POR_DOCUMENTO = {}
TOKENS_POR_DOCUMENTO = {}


class FakeDocumentoContratualRepository:
    def __init__(self, db):
        pass

    def get_by_id(self, documento_id):
        return DOCUMENTOS.get(documento_id)


class FakeDocumentoContratualVersaoRepository:
    def __init__(self, db):
        pass

    def list_by_documento(self, documento_id):
        return VERSOES_POR_DOCUMENTO.get(documento_id, [])


class FakeSolicitacaoAlteracaoContratualRepository:
    def __init__(self, db):
        pass

    def list_by_documento(self, documento_id):
        return SOLICITACOES_POR_DOCUMENTO.get(documento_id, [])


class FakeTokenAprovacaoContratualRepository:
    def __init__(self, db):
        pass

    def list_by_documento(self, documento_id):
        return TOKENS_POR_DOCUMENTO.get(documento_id, [])


class FakeDb:
    """Só o suficiente de `Session` pro use case: registra `delete` (na
    ordem) e decide se `commit` estoura `IntegrityError` (simula uma FK que
    o teste não listou de propósito)."""

    def __init__(self, falhar_no_commit=False):
        self.deletados = []
        self.falhar_no_commit = falhar_no_commit
        self.commitado = False
        self.rollback_chamado = False

    def delete(self, obj):
        self.deletados.append(obj)

    def commit(self):
        if self.falhar_no_commit:
            raise IntegrityError("stmt", {}, Exception("fk violation"))
        self.commitado = True

    def rollback(self):
        self.rollback_chamado = True


@pytest.fixture(autouse=True)
def _mundo(monkeypatch):
    DOCUMENTOS.clear()
    VERSOES_POR_DOCUMENTO.clear()
    SOLICITACOES_POR_DOCUMENTO.clear()
    TOKENS_POR_DOCUMENTO.clear()

    modulo = "src.use_cases.documento_contratual.hard_deletar_documento"
    monkeypatch.setattr(f"{modulo}.DocumentoContratualRepository", FakeDocumentoContratualRepository)
    monkeypatch.setattr(f"{modulo}.DocumentoContratualVersaoRepository", FakeDocumentoContratualVersaoRepository)
    monkeypatch.setattr(f"{modulo}.SolicitacaoAlteracaoContratualRepository", FakeSolicitacaoAlteracaoContratualRepository)
    monkeypatch.setattr(f"{modulo}.TokenAprovacaoContratualRepository", FakeTokenAprovacaoContratualRepository)


def test_documento_nao_encontrado_levanta_regra_de_negocio():
    db = FakeDb()
    with pytest.raises(RegraDeNegocioError):
        HardDeletarDocumentoContratualUseCase(db).execute(999)


def test_apaga_documento_assinado_e_arquivado_com_todo_o_historico():
    documento = SimpleNamespace(id=7, projeto_id=72, status="assinado_e_arquivado")
    versao = SimpleNamespace(id=2, documento_id=7)
    solicitacao = SimpleNamespace(id=1, documento_id=7, versao_id=2)
    token = SimpleNamespace(id=1, documento_id=7, versao_id=2)
    DOCUMENTOS[7] = documento
    VERSOES_POR_DOCUMENTO[7] = [versao]
    SOLICITACOES_POR_DOCUMENTO[7] = [solicitacao]
    TOKENS_POR_DOCUMENTO[7] = [token]

    db = FakeDb()
    HardDeletarDocumentoContratualUseCase(db).execute(7)

    # Ordem: filhos com FK pra versão (solicitação, token) saem antes da
    # versão, que sai antes do documento — senão a FK de verdade barraria.
    assert db.deletados.index(solicitacao) < db.deletados.index(versao)
    assert db.deletados.index(token) < db.deletados.index(versao)
    assert db.deletados.index(versao) < db.deletados.index(documento)
    assert db.commitado is True


def test_nao_apaga_nada_do_projeto():
    """Nada no use case referencia `ProjetoRepository`/apaga `projeto` — só
    os quatro repositórios do próprio documento. Se algum dia alguém
    importar um repositório de projeto aqui, é regressão."""
    import src.use_cases.documento_contratual.hard_deletar_documento as modulo

    assert not hasattr(modulo, "ProjetoRepository")


def test_erro_de_integridade_no_commit_vira_resource_in_use_e_faz_rollback():
    documento = SimpleNamespace(id=8, projeto_id=None, status="assinado_e_arquivado")
    DOCUMENTOS[8] = documento

    db = FakeDb(falhar_no_commit=True)
    with pytest.raises(ResourceInUseError):
        HardDeletarDocumentoContratualUseCase(db).execute(8)
    assert db.rollback_chamado is True
