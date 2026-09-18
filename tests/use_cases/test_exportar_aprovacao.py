"""Exportar o rascunho pro cliente aprovar (§ Contratos, 2026-09-18).

Mesmo idioma dos vizinhos: `__new__` + repositórios fake, notificação
trocada por um no-op (não é o que este teste cobre).
"""

from types import SimpleNamespace

import pytest

import src.use_cases.documento_contratual.exportar_aprovacao as exportar_mod
from src.use_cases.documento_contratual.exportar_aprovacao import (
    ExportarAprovacaoDocumentoContratualUseCase,
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


class FakeVersaoRepo:
    def __init__(self, versao):
        self._versao = versao

    def ultima_versao_obj(self, _documento_id):
        return self._versao


class FakeTokenRepo:
    def __init__(self):
        self.criados = []

    def create(self, **kwargs):
        token = SimpleNamespace(**kwargs)
        self.criados.append(token)
        return token


def documento(tipo="contrato", status="em_revisao_interna", telefone=""):
    projeto = SimpleNamespace(nome="Projeto Alfa", criado_por=None)
    dados = {"contratante": {"representante": {"telefone": telefone}}}
    return SimpleNamespace(id=1, tipo=tipo, status=status, dados=dados, projeto=projeto)


_SEM_VERSAO = object()


def montar(doc, versao=_SEM_VERSAO, monkeypatch=None):
    monkeypatch.setattr(exportar_mod, "documento_liberado_para_cliente", lambda *a, **k: None)
    uc = ExportarAprovacaoDocumentoContratualUseCase.__new__(ExportarAprovacaoDocumentoContratualUseCase)
    uc.db = None
    uc.documentos = FakeDocumentoRepo(doc)
    uc.versoes = FakeVersaoRepo(SimpleNamespace(id=9) if versao is _SEM_VERSAO else versao)
    uc.tokens = FakeTokenRepo()
    return uc


class TestExecute:
    def test_gera_token_e_muda_status(self, monkeypatch):
        doc = documento()
        uc = montar(doc, monkeypatch=monkeypatch)

        resultado = uc.execute(1)

        assert doc.status == "aguardando_aprovacao_cliente"
        assert resultado["token"]
        assert resultado["link_aprovacao"].endswith(f"/aprovacao/{resultado['token']}")
        assert uc.tokens.criados[0].documento_id == 1
        assert uc.tokens.criados[0].versao_id == 9

    def test_recusa_fora_de_em_revisao_interna(self, monkeypatch):
        doc = documento(status="aguardando_preenchimento")
        uc = montar(doc, monkeypatch=monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="em_revisao_interna"):
            uc.execute(1)

    def test_recusa_sem_nenhuma_versao_gerada(self, monkeypatch):
        doc = documento()
        uc = montar(doc, versao=None, monkeypatch=monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="Nenhum rascunho"):
            uc.execute(1)

    def test_link_whatsapp_so_existe_com_telefone(self, monkeypatch):
        sem_telefone = montar(documento(telefone=""), monkeypatch=monkeypatch)
        assert sem_telefone.execute(1)["link_whatsapp"] is None

        com_telefone = montar(documento(telefone="11999998888"), monkeypatch=monkeypatch)
        link = com_telefone.execute(1)["link_whatsapp"]
        assert link is not None
        assert "wa.me/5511999998888" in link


class TestRecusarAssinaturaTep:
    def test_gera_link_novo_a_partir_de_aprovado_pelo_cliente(self, monkeypatch):
        doc = documento(tipo="tep", status="aprovado_pelo_cliente")
        uc = montar(doc, monkeypatch=monkeypatch)

        resultado = uc.recusar_assinatura_tep(1)

        assert doc.status == "aguardando_aprovacao_cliente"
        assert resultado["token"]

    def test_so_se_aplica_ao_tep(self, monkeypatch):
        doc = documento(tipo="contrato", status="aprovado_pelo_cliente")
        uc = montar(doc, monkeypatch=monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="só se aplica ao TEP"):
            uc.recusar_assinatura_tep(1)

    def test_so_a_partir_de_aprovado_pelo_cliente(self, monkeypatch):
        doc = documento(tipo="tep", status="em_revisao_interna")
        uc = montar(doc, monkeypatch=monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="aprovado_pelo_cliente"):
            uc.recusar_assinatura_tep(1)
