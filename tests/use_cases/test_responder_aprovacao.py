"""Resposta do cliente na tela pública de aprovação (§ Contratos, 2026-09-18).

Endpoint sem login: os limites de trechos citados são o que mais importa
testar aqui, junto da máquina de estados.
"""

from types import SimpleNamespace

import pytest

import src.use_cases.documento_contratual.responder_aprovacao as responder_mod
from src.use_cases.documento_contratual.responder_aprovacao import (
    ResponderAprovacaoRequest,
    ResponderAprovacaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


class FakeTokenRepo:
    def __init__(self, registro):
        self._registro = registro
        self.usados = []

    def get_by_token(self, _token):
        return self._registro

    def marcar_usado(self, registro):
        self.usados.append(registro)
        registro.usado = True
        return registro


class FakeDocumentoRepo:
    def __init__(self, documento):
        self._documento = documento

    def get_by_id(self, _id):
        return self._documento

    def update(self, _id, **kwargs):
        for chave, valor in kwargs.items():
            setattr(self._documento, chave, valor)
        return self._documento


class FakeSolicitacaoRepo:
    def __init__(self):
        self.criadas = []

    def create(self, **kwargs):
        solicitacao = SimpleNamespace(**kwargs)
        self.criadas.append(solicitacao)
        return solicitacao


def token(usado=False, documento_id=1, versao_id=9):
    return SimpleNamespace(usado=usado, documento_id=documento_id, versao_id=versao_id)


def documento(status="aguardando_aprovacao_cliente"):
    return SimpleNamespace(id=1, status=status)


def montar(tok, doc, monkeypatch):
    monkeypatch.setattr(responder_mod, "cliente_respondeu", lambda *a, **k: None)
    uc = ResponderAprovacaoUseCase.__new__(ResponderAprovacaoUseCase)
    uc.db = None
    uc.tokens = FakeTokenRepo(tok)
    uc.documentos = FakeDocumentoRepo(doc)
    uc.solicitacoes = FakeSolicitacaoRepo()
    return uc


class TestAprovar:
    def test_aprova_e_marca_token_usado(self, monkeypatch):
        tok, doc = token(), documento()
        uc = montar(tok, doc, monkeypatch)

        resultado = uc.execute(tok, ResponderAprovacaoRequest(acao="aprovar"))

        assert resultado == {"ok": True}
        assert doc.status == "aprovado_pelo_cliente"
        assert tok.usado is True

    def test_recusa_token_ja_usado(self, monkeypatch):
        tok, doc = token(usado=True), documento()
        uc = montar(tok, doc, monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="já foi usado"):
            uc.execute("x", ResponderAprovacaoRequest(acao="aprovar"))

    def test_recusa_token_inexistente(self, monkeypatch):
        uc = montar(None, documento(), monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="Link inválido"):
            uc.execute("x", ResponderAprovacaoRequest(acao="aprovar"))


class TestSolicitarAlteracao:
    def test_cria_solicitacao_e_muda_status(self, monkeypatch):
        tok, doc = token(), documento()
        uc = montar(tok, doc, monkeypatch)

        uc.execute(tok, ResponderAprovacaoRequest(acao="alteracao", texto="Ajustar cláusula 5"))

        assert doc.status == "alteracao_solicitada"
        assert uc.solicitacoes.criadas[0].texto == "Ajustar cláusula 5"
        assert uc.solicitacoes.criadas[0].documento_id == 1
        assert uc.solicitacoes.criadas[0].versao_id == 9

    def test_exige_texto(self, monkeypatch):
        tok, doc = token(), documento()
        uc = montar(tok, doc, monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="Descreva o que precisa"):
            uc.execute(tok, ResponderAprovacaoRequest(acao="alteracao", texto=""))

    def test_recusa_mais_de_20_trechos(self, monkeypatch):
        tok, doc = token(), documento()
        uc = montar(tok, doc, monkeypatch)
        trechos = [f"trecho {i}" for i in range(21)]

        with pytest.raises(RegraDeNegocioError, match="Máximo de 20"):
            uc.execute(tok, ResponderAprovacaoRequest(acao="alteracao", texto="x", trechos=trechos))

    def test_recusa_trecho_maior_que_1000_caracteres(self, monkeypatch):
        tok, doc = token(), documento()
        uc = montar(tok, doc, monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="1000 caracteres"):
            uc.execute(
                tok, ResponderAprovacaoRequest(acao="alteracao", texto="x", trechos=["a" * 1001])
            )

    def test_ignora_trechos_vazios(self, monkeypatch):
        tok, doc = token(), documento()
        uc = montar(tok, doc, monkeypatch)

        uc.execute(tok, ResponderAprovacaoRequest(acao="alteracao", texto="x", trechos=["  ", "ok"]))

        assert uc.solicitacoes.criadas[0].trechos == ["ok"]
