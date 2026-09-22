"""Contrato institucional (Agro etc.) — documento avulso, sem projeto de
entrega por trás (§ Contratos, 2026-09-21).

Mesmo idioma dos vizinhos: repositório fake trocado no MÓDULO do use case.
"""

import pytest

import src.use_cases.documento_contratual.criar_institucional as mod
from src.use_cases.documento_contratual.criar_institucional import (
    CriarDocumentoInstitucionalRequest,
    CriarDocumentoInstitucionalUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


class FakeDocumentoRepo:
    def __init__(self, db):
        pass

    def create(self, **kwargs):
        self.criado = kwargs
        return kwargs


def montar(monkeypatch):
    repo = FakeDocumentoRepo(db=None)
    monkeypatch.setattr(mod, "DocumentoContratualRepository", lambda db: repo)
    return CriarDocumentoInstitucionalUseCase(db=None), repo


class TestCriarDocumentoInstitucional:
    def test_cria_sem_projeto_id_com_nome_e_cliente_externos(self, monkeypatch):
        uc, repo = montar(monkeypatch)
        request = CriarDocumentoInstitucionalRequest(
            nome_projeto="Parceria Agro Insper", cliente="Agro Ltda", tipo="nda"
        )

        uc.execute(request)

        assert repo.criado["projeto_id"] is None
        assert repo.criado["nome_projeto_externo"] == "Parceria Agro Insper"
        assert repo.criado["cliente_externo"] == "Agro Ltda"
        assert repo.criado["tipo"] == "nda"
        assert repo.criado["status"] == "aguardando_preenchimento"
        assert repo.criado["confirmado"] is False

    def test_dados_iniciais_nascem_em_branco(self, monkeypatch):
        uc, repo = montar(monkeypatch)
        request = CriarDocumentoInstitucionalRequest(nome_projeto="X", cliente=None, tipo="contrato")

        uc.execute(request)

        assert repo.criado["dados"]["contratante"]["razao_social"] == ""

    def test_tipo_desconhecido_e_erro(self, monkeypatch):
        uc, _ = montar(monkeypatch)
        request = CriarDocumentoInstitucionalRequest(nome_projeto="X", cliente=None, tipo="inexistente")

        with pytest.raises(RegraDeNegocioError):
            uc.execute(request)
