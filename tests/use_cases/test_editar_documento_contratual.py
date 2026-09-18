"""Editar dados e confirmar preenchimento de um documento jurídico
(§ Contratos, 2026-09-16) — duas janelas de edição, não uma.

Mesmo padrão dos vizinhos: `__new__` + repositório fake.
"""

from types import SimpleNamespace

import pytest

import src.use_cases.documento_contratual.confirmar_preenchimento as confirmar_preenchimento_mod
from src.use_cases.documento_contratual.atualizar_dados import (
    AtualizarDadosDocumentoContratualUseCase,
)
from src.use_cases.documento_contratual.confirmar_preenchimento import (
    ConfirmarPreenchimentoDocumentoContratualUseCase,
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


def documento(status="aguardando_preenchimento", confirmado=False, dados=None):
    return SimpleNamespace(id=1, status=status, confirmado=confirmado, dados=dados or {})


def montar_atualizar(doc):
    uc = AtualizarDadosDocumentoContratualUseCase.__new__(AtualizarDadosDocumentoContratualUseCase)
    uc.documentos = FakeDocumentoRepo(doc)
    return uc


def montar_confirmar(doc, monkeypatch):
    # A notificação (`documento_pronto_para_gerar`) não é o que este teste
    # cobre — vira no-op, mesmo padrão de `test_entrada_solicitacao.py` pra
    # não exigir um banco de verdade só pra montar destinatários.
    monkeypatch.setattr(confirmar_preenchimento_mod, "documento_pronto_para_gerar", lambda *a, **k: None)
    uc = ConfirmarPreenchimentoDocumentoContratualUseCase.__new__(
        ConfirmarPreenchimentoDocumentoContratualUseCase
    )
    uc.db = None
    uc.documentos = FakeDocumentoRepo(doc)
    return uc


class TestAtualizarDados:
    def test_quem_preencheu_edita_enquanto_nao_confirmou(self):
        doc = documento()
        uc = montar_atualizar(doc)

        atualizado = uc.execute(1, {"contratante": {"razao_social": "X"}}, pode_editar_livre=False)

        assert atualizado.dados == {"contratante": {"razao_social": "X"}}

    def test_quem_preencheu_nao_edita_depois_de_confirmado(self):
        doc = documento(confirmado=True)
        uc = montar_atualizar(doc)

        with pytest.raises(RegraDeNegocioError, match="já foi confirmado"):
            uc.execute(1, {}, pode_editar_livre=False)

    def test_quem_preencheu_nao_edita_fora_de_aguardando_preenchimento(self):
        doc = documento(status="em_revisao_interna")
        uc = montar_atualizar(doc)

        with pytest.raises(RegraDeNegocioError, match="Só quem preencheu"):
            uc.execute(1, {}, pode_editar_livre=False)

    def test_juridico_edita_mesmo_confirmado_e_em_revisao(self):
        doc = documento(status="em_revisao_interna", confirmado=True)
        uc = montar_atualizar(doc)

        atualizado = uc.execute(1, {"x": 1}, pode_editar_livre=True)

        assert atualizado.dados == {"x": 1}

    def test_ninguem_edita_depois_do_cliente_aprovar(self):
        doc = documento(status="aprovado_pelo_cliente")
        uc = montar_atualizar(doc)

        with pytest.raises(RegraDeNegocioError, match="cliente já aprovou"):
            uc.execute(1, {}, pode_editar_livre=True)

    def test_ninguem_edita_documento_assinado_e_arquivado(self):
        doc = documento(status="assinado_e_arquivado")
        uc = montar_atualizar(doc)

        with pytest.raises(RegraDeNegocioError, match="cliente já aprovou"):
            uc.execute(1, {}, pode_editar_livre=True)


class TestConfirmarPreenchimento:
    def test_confirma_um_documento_aguardando_preenchimento(self, monkeypatch):
        doc = documento()
        uc = montar_confirmar(doc, monkeypatch)

        confirmado = uc.execute(1)

        assert confirmado.confirmado is True

    def test_nao_confirma_duas_vezes(self, monkeypatch):
        doc = documento(confirmado=True)
        uc = montar_confirmar(doc, monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="já foi confirmado"):
            uc.execute(1)

    def test_nao_confirma_fora_de_aguardando_preenchimento(self, monkeypatch):
        doc = documento(status="em_revisao_interna")
        uc = montar_confirmar(doc, monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="aguardando preenchimento"):
            uc.execute(1)
