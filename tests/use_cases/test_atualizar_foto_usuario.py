"""Foto de perfil: sempre a própria, e com uma validação mínima do que chega.

O `data:image/...;base64,...` inteiro vem do cliente já redimensionado — o
backend não decodifica a imagem em si, só confere que tem cara de imagem e
que não é grande demais. Dublê escrito à mão, mesmo idioma de
`test_email_notificacao.py`.
"""

import base64
from types import SimpleNamespace

import pytest

from src.use_cases.usuario import atualizar_foto
from src.use_cases.usuario.atualizar_foto import (
    AtualizarFotoUsuarioUseCase,
    RemoverFotoUsuarioUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

USUARIO = SimpleNamespace(id=5)

PNG_1X1 = base64.b64encode(b"conteudo-fake-de-imagem").decode()
DATA_URI_VALIDA = f"data:image/png;base64,{PNG_1X1}"


class UsuarioRepositoryFake:
    def __init__(self, db=None):
        self.atualizacoes = []

    def update(self, usuario_id, **campos):
        self.atualizacoes.append((usuario_id, campos))
        return SimpleNamespace(
            id=usuario_id,
            nome="Bia Martins",
            email_insper="bia@al.insper.edu.br",
            posicao="consultor",
            status="ativo",
            ativo=True,
            coordenador_vendas=False,
            bdr=False,
            semestre_graduacao=None,
            senha_provisoria=False,
            foto=campos.get("foto"),
        )


@pytest.fixture
def repo(monkeypatch):
    fake = UsuarioRepositoryFake()
    monkeypatch.setattr(atualizar_foto, "UsuarioRepository", lambda db: fake)
    return fake


class TestAtualizar:
    def test_grava_a_data_uri_no_dono_certo(self, repo):
        resultado = AtualizarFotoUsuarioUseCase(db=None).execute(USUARIO, DATA_URI_VALIDA)
        assert repo.atualizacoes == [(5, {"foto": DATA_URI_VALIDA})]
        assert resultado["foto"] == DATA_URI_VALIDA

    def test_recusa_formato_que_nao_e_imagem(self, repo):
        with pytest.raises(RegraDeNegocioError, match="não reconhecido"):
            AtualizarFotoUsuarioUseCase(db=None).execute(USUARIO, "data:text/plain;base64,eGl4")
        assert repo.atualizacoes == []

    def test_recusa_imagem_grande_demais(self, repo):
        enorme = "data:image/png;base64," + ("A" * (2 * 1024 * 1024 + 1))
        with pytest.raises(RegraDeNegocioError, match="grande demais"):
            AtualizarFotoUsuarioUseCase(db=None).execute(USUARIO, enorme)
        assert repo.atualizacoes == []

    def test_recusa_base64_corrompido(self, repo):
        with pytest.raises(RegraDeNegocioError, match="corrompida"):
            AtualizarFotoUsuarioUseCase(db=None).execute(USUARIO, "data:image/png;base64,não-é-base64!!!")
        assert repo.atualizacoes == []


class TestRemover:
    def test_apaga_a_foto_do_dono_certo(self, repo):
        RemoverFotoUsuarioUseCase(db=None).execute(USUARIO)
        assert repo.atualizacoes == [(5, {"foto": None})]
