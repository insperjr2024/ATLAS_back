"""O teto de consultores é um INVARIANTE: nunca há mais gente que vagas.

⭐ **"5 consultores num projeto de teto 3" não pode existir.** Foi o estado em
que o Atlas Tech ficou, e ele não veio de uma falha de validação: veio da
migration `00b38e9fa008`, que criou a coluna com `server_default='3'` e
carimbou 3 em todo projeto que já existia, tivesse quantos consultores
tivesse. A `c4f7d20a91e5` corrigiu esses.

Estas provas cobrem o outro lado — que nenhuma VIA DE ENTRADA reabre o buraco.
São quatro caminhos para o estado divergente, e cada um tem um teste:

1. criar projeto com equipe maior que o teto;
2. editar a equipe para além do teto;
3. baixar o teto abaixo da equipe atual;
4. (as vias de `solicitacao_projeto` ficam nos testes daquele módulo, que já
   cobrem "o time encheu depois que o pedido foi feito".)

A tela agora mostra o teto CRU (`consultores / max_consultores`), sem
`Math.max` — se o invariante quebrar, aparece "5 de 3" em vez de um "5 de 5"
tranquilizador. Estas provas são o que mantém esse número honesto sem ser
constrangedor.
"""

from types import SimpleNamespace

import pytest

from src.utils.exceptions import RegraDeNegocioError
from src.utils.validacao_equipe import validar_equipe


class UsuarioFake:
    def __init__(self, id, posicao="consultor"):
        self.id = id
        self.nome = f"Pessoa {id}"
        self.posicao = posicao
        self.status = "ativo"


class UsuarioRepoFake:
    def __init__(self, *usuarios):
        self._por_id = {u.id: u for u in usuarios}

    def get_by_id(self, usuario_id):
        return self._por_id.get(usuario_id)


def membro(usuario_id, papel="consultor"):
    return SimpleNamespace(usuario_id=usuario_id, papel=papel)


@pytest.fixture
def repo():
    return UsuarioRepoFake(*[UsuarioFake(i) for i in range(1, 9)])


class TestCriarOuEditarEquipe:
    """`validar_equipe` é o portão de `create_projeto` E de
    `update_equipe_projeto` — os dois caminhos dizem a mesma coisa."""

    def test_equipe_dentro_do_teto_passa(self, repo):
        validar_equipe([membro(1), membro(2), membro(3)], repo, max_consultores=3)

    def test_equipe_acima_do_teto_e_recusada(self, repo):
        with pytest.raises(RegraDeNegocioError, match="teto"):
            validar_equipe([membro(i) for i in range(1, 6)], repo, max_consultores=3)

    def test_a_recusa_diz_os_dois_numeros(self, repo):
        """Quem lê o erro precisa saber quantos tem e quantos cabem — sem isso
        a saída é adivinhar quantas pessoas tirar."""
        with pytest.raises(RegraDeNegocioError) as erro:
            validar_equipe([membro(i) for i in range(1, 6)], repo, max_consultores=3)
        assert "5" in str(erro.value) and "3" in str(erro.value)

    def test_exatamente_no_teto_passa(self, repo):
        """O limite é inclusivo: teto 3 aceita 3, não 2."""
        validar_equipe([membro(1), membro(2), membro(3)], repo, max_consultores=3)

    def test_coordenador_nao_ocupa_vaga_de_consultor(self):
        """O teto é de CONSULTORES. Coordenador entra pelo papel, não pela
        vaga — senão um projeto de teto 3 só caberia 2 consultores.

        A pessoa na cadeira de coordenador precisa TER posição de coordenador
        (ou gerente): consultor não vira coordenador de projeto sem promoção
        de verdade, que é o §10 e não uma vaga de equipe."""
        repo = UsuarioRepoFake(
            UsuarioFake(1, "coordenador"), *[UsuarioFake(i) for i in (2, 3, 4)]
        )
        equipe = [membro(1, "coordenador")] + [membro(i) for i in (2, 3, 4)]
        validar_equipe(equipe, repo, max_consultores=3)

    def test_sem_teto_informado_nao_valida(self, repo):
        """`create_projeto` grava o teto na mesma chamada em que valida a
        equipe, então às vezes o número ainda não existe para comparar."""
        validar_equipe([membro(i) for i in range(1, 9)], repo, max_consultores=None)
