"""Login com a senha provisória: aceitar o código mesmo quando o e-mail
mudou a APARÊNCIA dele.

A provisória sai no formato `XXXXX-XXXXX`, vai por e-mail e é lida e digitada
à mão. Cliente de e-mail quebra linha no meio, copiar de um bloco com
`letter-spacing` traz espaço entre os caracteres, o "auto-formatar" troca o
hífen por um travessão. Nada disso muda o código, e a comparação tolerante
só vale para a provisória: a senha própria pode ter espaço ou minúscula de
propósito.
"""

import pytest

from src.use_cases.auth.login import LoginRequest, LoginUseCase
from src.utils.exceptions import RegraDeNegocioError
from src.utils.senha import hash_senha

SENHA = "ABCDE-FGHJK"


class UsuarioFake:
    def __init__(self, senha_provisoria=True, ativo=True):
        self.id = 1
        self.email_insper = "bia@al.insper.edu.br"
        self.senha_hash = hash_senha(SENHA)
        self.senha_provisoria = senha_provisoria
        self.ativo = ativo


class RepoFake:
    def __init__(self, usuario):
        self._usuario = usuario

    def get_by_email_insper(self, email):
        return self._usuario if email == self._usuario.email_insper else None


def login(usuario, senha):
    uc = LoginUseCase(db=None, usuario_repository=RepoFake(usuario))
    return uc.execute(LoginRequest(email_insper=usuario.email_insper, senha=senha))


class TestFormasEquivalentes:
    @pytest.mark.parametrize(
        "digitada",
        [
            "ABCDE-FGHJK",           # exata
            "ABCDE - FGHJK",         # espaço em volta do hífen
            "ABC DE-FG HJK",         # espaço no meio (letter-spacing / quebra de linha)
            "A B C D E - F G H J K",  # espaço entre todos os caracteres
            "ABCDE–FGHJK",      # en dash no lugar do hífen
            "ABCDE—FGHJK",      # em dash
            "abcde-fghjk",            # minúsculo
            "ABCDEFGHJK",             # hífen perdido
            "ABCDE FGHJK",            # hífen virou espaço
            "  ABCDE-FGHJK \n",      # espaço/quebra nas pontas
        ],
    )
    def test_aceita(self, digitada):
        assert "access_token" in login(UsuarioFake(), digitada)

    def test_recusa_codigo_errado(self):
        with pytest.raises(RegraDeNegocioError, match="Email ou senha incorretos"):
            login(UsuarioFake(), "ZZZZZ-ZZZZZ")


class TestSoValeParaProvisoria:
    def test_senha_propria_nao_ganha_a_tolerancia(self):
        """Fora do primeiro acesso, `ABCDE FGHJK` é outra senha, não o mesmo
        código com espaço."""
        usuario = UsuarioFake(senha_provisoria=False)
        with pytest.raises(RegraDeNegocioError, match="Email ou senha incorretos"):
            login(usuario, "ABCDE FGHJK")

    def test_senha_propria_exata_ainda_entra(self):
        usuario = UsuarioFake(senha_provisoria=False)
        assert "access_token" in login(usuario, SENHA)


class TestDesativado:
    def test_codigo_certo_mas_conta_desativada(self):
        with pytest.raises(RegraDeNegocioError, match="desativado"):
            login(UsuarioFake(ativo=False), "ABCDE FGHJK")
