from dataclasses import dataclass

import pytest

from src.utils.exceptions import RegraDeNegocioError
from src.utils.validacao_equipe import validar_equipe


@dataclass
class UsuarioFake:
    id: int
    nome: str
    posicao: str


@dataclass
class MembroFake:
    usuario_id: int
    papel: str


class UsuarioRepositoryFake:
    def __init__(self, *usuarios):
        self._por_id = {u.id: u for u in usuarios}

    def get_by_id(self, usuario_id):
        return self._por_id.get(usuario_id)


COORD = UsuarioFake(1, "Ana Souza", "coordenador")
OUTRO_COORD = UsuarioFake(2, "Bruno Dias", "coordenador")
CONSULTOR = UsuarioFake(3, "Bia Martins", "consultor")
OUTRO_CONSULTOR = UsuarioFake(4, "Caio Ferreira", "consultor")
GERENTE = UsuarioFake(5, "Gil Nunes", "gerente")
DIRETOR = UsuarioFake(6, "Dani Alves", "diretor")

REPO = UsuarioRepositoryFake(
    COORD, OUTRO_COORD, CONSULTOR, OUTRO_CONSULTOR, GERENTE, DIRETOR
)


class TestQuantidadeDeCoordenadores:
    def test_equipe_sem_coordenador_e_recusada(self):
        equipe = [MembroFake(CONSULTOR.id, "consultor")]
        with pytest.raises(RegraDeNegocioError, match="exatamente 1 coordenador"):
            validar_equipe(equipe, REPO)

    def test_equipe_com_dois_coordenadores_e_recusada(self):
        equipe = [
            MembroFake(COORD.id, "coordenador"),
            MembroFake(OUTRO_COORD.id, "coordenador"),
        ]
        with pytest.raises(RegraDeNegocioError, match="exatamente 1 coordenador"):
            validar_equipe(equipe, REPO)

    def test_projeto_sem_nenhum_consultor_e_recusado(self):
        with pytest.raises(RegraDeNegocioError, match="pelo menos 1 consultor"):
            validar_equipe([MembroFake(COORD.id, "coordenador")], REPO)


class TestPosicaoExigidaPorPapel:
    def test_coordenador_precisa_ter_a_posicao_coordenador(self):
        equipe = [MembroFake(COORD.id, "coordenador"), MembroFake(CONSULTOR.id, "consultor")]
        validar_equipe(equipe, REPO)

    def test_consultor_nao_pode_ser_coordenador_do_projeto(self):
        equipe = [MembroFake(CONSULTOR.id, "coordenador")]
        with pytest.raises(RegraDeNegocioError, match="Bia Martins"):
            validar_equipe(equipe, REPO)

    def test_coordenador_pode_entrar_como_consultor_de_outro_projeto(self):
        """Hierarquia: coordenador cobre a vaga de consultor, nunca o
        contrário (§10 — quem sobe de posição não pode "descer" um papel)."""
        equipe = [
            MembroFake(COORD.id, "coordenador"),
            MembroFake(OUTRO_COORD.id, "consultor"),
        ]
        validar_equipe(equipe, REPO)

    @pytest.mark.parametrize("usuario", [GERENTE, DIRETOR])
    def test_gerencia_e_diretoria_nao_podem_ser_coordenador_do_projeto(self, usuario):
        with pytest.raises(RegraDeNegocioError, match=usuario.nome):
            validar_equipe([MembroFake(usuario.id, "coordenador")], REPO)

    @pytest.mark.parametrize("usuario", [GERENTE, DIRETOR])
    def test_gerencia_e_diretoria_podem_ocupar_a_equipe_como_consultor(self, usuario):
        """Diferente de coordenador: como consultor elas cabem — a hierarquia
        (diretor > gerente > coordenador > consultor) cobre a vaga de baixo."""
        equipe = [MembroFake(COORD.id, "coordenador"), MembroFake(usuario.id, "consultor")]
        validar_equipe(equipe, REPO)


class TestAlocacaoEmVariosProjetos:
    """Nada aqui olha os outros projetos da pessoa: coordenador e consultor
    podem estar alocados em quantos projetos forem necessários."""

    def test_mesma_equipe_validada_repetidas_vezes_continua_valida(self):
        equipe = [
            MembroFake(COORD.id, "coordenador"),
            MembroFake(CONSULTOR.id, "consultor"),
            MembroFake(OUTRO_CONSULTOR.id, "consultor"),
        ]
        for _ in range(3):
            validar_equipe(equipe, REPO)


class TestEntradasInvalidas:
    def test_usuario_inexistente_e_recusado(self):
        equipe = [MembroFake(COORD.id, "coordenador"), MembroFake(999, "consultor")]
        with pytest.raises(RegraDeNegocioError, match="não encontrado"):
            validar_equipe(equipe, REPO)

    def test_papel_desconhecido_e_recusado(self):
        equipe = [MembroFake(COORD.id, "coordenador"), MembroFake(CONSULTOR.id, "estagiario")]
        with pytest.raises(RegraDeNegocioError, match="Papel inválido"):
            validar_equipe(equipe, REPO)
