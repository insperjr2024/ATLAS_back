"""⭐ A plataforma nunca pode ficar sem quem edite permissões.

`pode_administrar_permissoes` é a única caixa que se auto-tranca: ela é o que
dá acesso à tela de permissões, então desligar a última deixa a plataforma num
estado que ela própria não conserta — só mexendo no banco à mão.

A regra protegida aqui não é "sobrar uma POSIÇÃO com a caixa", e sim sobrar uma
PESSOA ATIVA: posição marcada sem ninguém dentro dela é uma porta que não abre,
e foi justamente esse o buraco que quase custou o acesso em 2026-09-02.

⚠ O que a regra NÃO faz: impedir a diretoria de tirar a caixa de si mesma.
Delegar e sair é legítimo — só não pode ser o último a apagar a luz.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.posicao_permissao.update_posicao_permissao import (
    UpdatePosicaoPermissaoRequest,
    UpdatePosicaoPermissaoUseCase,
)
from src.utils.exceptions import CODIGO_ULTIMO_ADMINISTRADOR, RegraDeNegocioError


def linha(posicao, administra):
    return SimpleNamespace(posicao=posicao, pode_administrar_permissoes=administra)


def usuario(posicao, status="ativo"):
    return SimpleNamespace(posicao=posicao, status=status)


@pytest.fixture
def desmarcar(monkeypatch):
    """`(executar, estado)` com os dois repositórios trocados por dublês."""

    def _montar(linhas, usuarios):
        caso = UpdatePosicaoPermissaoUseCase(db=None)
        estado = {"gravou": None}

        def _update(posicao, **dados):
            estado["gravou"] = (posicao, dados)
            return linha(posicao, dados.get("pode_administrar_permissoes", False))

        caso.repository = SimpleNamespace(get_all=lambda: linhas, update=_update)
        caso.usuario_repository = SimpleNamespace(
            get_por_posicoes=lambda *posicoes: [u for u in usuarios if u.posicao in posicoes]
        )
        monkeypatch.setattr(
            "src.use_cases.posicao_permissao.update_posicao_permissao"
            ".serializar_posicao_permissao",
            lambda registro: {"posicao": registro.posicao},
        )

        def _executar(posicao, **campos):
            return caso.execute(posicao, UpdatePosicaoPermissaoRequest(**campos))

        return _executar, estado

    return _montar


def test_recusa_quando_e_a_ultima_porta(desmarcar):
    executar, estado = desmarcar(
        linhas=[linha("diretor_projetos", True), linha("gerente", False)],
        usuarios=[usuario("diretor_projetos")],
    )

    with pytest.raises(RegraDeNegocioError) as excecao:
        executar("diretor_projetos", pode_administrar_permissoes=False)

    assert excecao.value.codigo == CODIGO_ULTIMO_ADMINISTRADOR
    assert estado["gravou"] is None, "não pode ter gravado antes de recusar"


def test_permite_quando_outra_posicao_tem_gente_ativa(desmarcar):
    executar, estado = desmarcar(
        linhas=[linha("diretor_projetos", True), linha("diretor_pessoas", True)],
        usuarios=[usuario("diretor_projetos"), usuario("diretor_pessoas")],
    )

    executar("diretor_projetos", pode_administrar_permissoes=False)

    assert estado["gravou"][0] == "diretor_projetos"


def test_posicao_marcada_sem_ninguem_ativo_nao_conta_como_porta(desmarcar):
    """O buraco que a regra fecha: a caixa marcada numa posição vazia parece
    uma saída na tela de Configurações e não abre para ninguém."""
    executar, _ = desmarcar(
        linhas=[linha("diretor_projetos", True), linha("diretor_pessoas", True)],
        usuarios=[usuario("diretor_projetos"), usuario("diretor_pessoas", status="ex_membro")],
    )

    with pytest.raises(RegraDeNegocioError) as excecao:
        executar("diretor_projetos", pode_administrar_permissoes=False)

    assert excecao.value.codigo == CODIGO_ULTIMO_ADMINISTRADOR


def test_nao_atrapalha_quem_esta_ligando_a_caixa(desmarcar):
    executar, estado = desmarcar(
        linhas=[linha("diretor_projetos", True), linha("gerente", False)],
        usuarios=[usuario("diretor_projetos")],
    )

    executar("gerente", pode_administrar_permissoes=True)

    assert estado["gravou"][0] == "gerente"


def test_nao_atrapalha_update_que_nem_menciona_a_caixa(desmarcar):
    """Marcar outra permissão qualquer não passa pela regra — o
    `exclude_unset` do request é o que separa "não mandou" de "mandou false"."""
    executar, estado = desmarcar(
        linhas=[linha("diretor_projetos", True)],
        usuarios=[usuario("diretor_projetos")],
    )

    executar("diretor_projetos", pode_criar_projeto=False)

    assert estado["gravou"][1] == {"pode_criar_projeto": False}
