"""⭐ Quem mexe na lista de escopos vendidos de um projeto (§4).

Era `require_gestao` — diretoria de projetos e gerência de frente. O
coordenador ficava de fora, e era ele quem descobria que faltava um escopo.
São exatamente dois agora, e a gerência PERDEU o acesso.

O que estes testes protegem é a linha entre as duas formas de entrar:

- **pela POSIÇÃO**, sem estar na equipe: só a diretoria de projetos, que
  enxerga o portfólio inteiro;
- **pelo PAPEL NO PROJETO**: o coordenador, e só o daquele projeto.

É a mesma régua do §8 e da confirmação de entrega. Responder diferente em cada
uma é o que o `permissao_escopo` existe para não deixar acontecer.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.projeto_escopo import permissao_escopo
from src.use_cases.projeto_escopo.permissao_escopo import (
    exigir_pode_editar_escopos,
    pode_editar_escopos,
)
from src.utils.exceptions import RegraDeNegocioError

PROJETO = 3

DIRETORA = SimpleNamespace(id=1, posicao="diretor_projetos")
DIRETOR_PESSOAS = SimpleNamespace(id=2, posicao="diretor_pessoas")
DIRETOR_VISUAL = SimpleNamespace(id=3, posicao="diretor")
GERENTE = SimpleNamespace(id=4, posicao="gerente")
ANA = SimpleNamespace(id=10, posicao="coordenador")
BRUNO = SimpleNamespace(id=11, posicao="coordenador")
CAIO = SimpleNamespace(id=12, posicao="consultor")


@pytest.fixture
def equipe(monkeypatch):
    """Monta a equipe do projeto 3. Ana coordena; Caio é consultor."""

    def _montar(membros=None):
        membros = membros if membros is not None else [
            SimpleNamespace(usuario_id=ANA.id, papel="coordenador"),
            SimpleNamespace(usuario_id=CAIO.id, papel="consultor"),
        ]

        class MembroFake:
            def __init__(self, db): pass
            def get_by_projeto(self, projeto_id, apenas_atuais=False):
                return membros if projeto_id == PROJETO else []

        monkeypatch.setattr(permissao_escopo, "ProjetoMembroRepository", MembroFake)

    return _montar


class TestEntraPelaPosicao:
    """Sem estar na equipe: só quem enxerga o portfólio e o conduz."""

    def test_diretoria_de_projetos_edita(self, equipe):
        equipe()

        assert pode_editar_escopos(PROJETO, DIRETORA, db=None) is True

    def test_gerencia_de_frente_nao_edita_mais(self, equipe):
        """⚠ Regressão DELIBERADA (2026-08-31, a pedido). A gerência entrava
        por `require_gestao`, junto da diretoria; agora pede ao coordenador do
        projeto ou à diretoria."""
        equipe()

        assert pode_editar_escopos(PROJETO, GERENTE, db=None) is False

    @pytest.mark.parametrize("quem", [DIRETOR_PESSOAS, DIRETOR_VISUAL])
    def test_as_outras_duas_diretorias_nao(self, equipe, quem):
        """`diretor_pessoas` cuida de gente e `diretor` só visualiza — nenhum
        dos dois conduz projeto."""
        equipe()

        assert pode_editar_escopos(PROJETO, quem, db=None) is False

    def test_gerente_que_coordena_o_projeto_edita(self, equipe):
        """A perda é da POSIÇÃO, não da pessoa: um gerente que ocupa a vaga de
        coordenador deste projeto entra pelo papel, como qualquer coordenador.
        (`validacao_equipe` permite exatamente esse caso.)"""
        equipe(membros=[SimpleNamespace(usuario_id=GERENTE.id, papel="coordenador")])

        assert pode_editar_escopos(PROJETO, GERENTE, db=None) is True


class TestEntraPeloPapel:
    def test_coordenador_do_projeto_edita(self, equipe):
        equipe()

        assert pode_editar_escopos(PROJETO, ANA, db=None) is True

    def test_coordenador_de_outro_projeto_nao(self, equipe):
        """⭐ O ponto de a checagem não ser só de posição: Bruno é coordenador
        na plataforma, mas não deste projeto."""
        equipe()

        assert pode_editar_escopos(PROJETO, BRUNO, db=None) is False

    def test_consultor_da_equipe_nao(self, equipe):
        equipe()

        assert pode_editar_escopos(PROJETO, CAIO, db=None) is False

    def test_coordenador_que_saiu_nao(self, equipe):
        """`apenas_atuais`: quem passou o bastão perde o direito na hora. O
        dublê devolve equipe vazia, que é o que o filtro produz."""
        equipe(membros=[])

        assert pode_editar_escopos(PROJETO, ANA, db=None) is False


class TestAMensagem:
    def test_recusa_diz_os_tres_caminhos(self, equipe):
        equipe()

        with pytest.raises(RegraDeNegocioError, match="coordenador deste projeto"):
            exigir_pode_editar_escopos(PROJETO, CAIO, db=None)

    def test_quem_pode_passa_sem_levantar(self, equipe):
        equipe()

        exigir_pode_editar_escopos(PROJETO, ANA, db=None)
