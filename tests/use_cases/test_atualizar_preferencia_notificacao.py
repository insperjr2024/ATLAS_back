"""Quais tipos de notificação a pessoa desligou do e-mail — só os opcionais
podem entrar na lista, os fixos recusam. Dublê escrito à mão, mesmo idioma
de `test_atualizar_foto_usuario.py`.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.usuario import atualizar_preferencia_notificacao
from src.use_cases.usuario.atualizar_preferencia_notificacao import (
    AtualizarPreferenciaNotificacaoRequest,
    AtualizarPreferenciaNotificacaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


class UsuarioRepositoryFake:
    def __init__(self, db=None):
        self.atualizacoes = []

    def update(self, usuario_id, **campos):
        self.atualizacoes.append((usuario_id, campos))
        return SimpleNamespace(
            id=usuario_id,
            notificacoes_email_desativadas=campos.get("notificacoes_email_desativadas"),
        )


@pytest.fixture
def repo(monkeypatch):
    fake = UsuarioRepositoryFake()
    monkeypatch.setattr(atualizar_preferencia_notificacao, "UsuarioRepository", lambda db: fake)
    return fake


class TestAtualizar:
    def test_grava_os_tipos_opcionais_desativados(self, repo):
        request = AtualizarPreferenciaNotificacaoRequest(
            desativadas=["entrega_registrada", "banca_aviso"]
        )
        resultado = AtualizarPreferenciaNotificacaoUseCase(db=None).execute(5, request)

        assert repo.atualizacoes == [
            (5, {"notificacoes_email_desativadas": ["entrega_registrada", "banca_aviso"]})
        ]
        assert resultado["notificacoes_email_desativadas"] == ["entrega_registrada", "banca_aviso"]

    def test_lista_vazia_liga_tudo_de_volta(self, repo):
        AtualizarPreferenciaNotificacaoUseCase(db=None).execute(
            5, AtualizarPreferenciaNotificacaoRequest(desativadas=[])
        )
        assert repo.atualizacoes == [(5, {"notificacoes_email_desativadas": []})]

    def test_recusa_tipo_fixo(self, repo):
        """`banca_remarcada` é fixo — aceitar em silêncio deixaria a pessoa
        achar que desligou algo que continua saindo sempre."""
        with pytest.raises(RegraDeNegocioError, match="banca_remarcada"):
            AtualizarPreferenciaNotificacaoUseCase(db=None).execute(
                5, AtualizarPreferenciaNotificacaoRequest(desativadas=["banca_remarcada"])
            )
        assert repo.atualizacoes == []

    def test_recusa_tipo_inexistente(self, repo):
        with pytest.raises(RegraDeNegocioError, match="tipo_que_nao_existe"):
            AtualizarPreferenciaNotificacaoUseCase(db=None).execute(
                5, AtualizarPreferenciaNotificacaoRequest(desativadas=["tipo_que_nao_existe"])
            )
        assert repo.atualizacoes == []

    def test_remove_duplicata_mantendo_a_ordem(self, repo):
        AtualizarPreferenciaNotificacaoUseCase(db=None).execute(
            5,
            AtualizarPreferenciaNotificacaoRequest(
                desativadas=["banca_aviso", "entrega_registrada", "banca_aviso"]
            ),
        )
        assert repo.atualizacoes == [
            (5, {"notificacoes_email_desativadas": ["banca_aviso", "entrega_registrada"]})
        ]
