"""§8 — as duas portas de trás que a Rodada 5 do roteiro encontrou.

1. **Troca de vaga.** `_excluidos` e a confirmação liam só a legada
   `equipe_projeto`, vazia para banca marcada pelo cronograma. Dava para
   convidar um consultor da própria equipe do projeto — ou deixar que ele
   confirmasse um pedido aberto — e ele virava avaliador da banca dele mesmo.
   Era o contorno da regra que `create_candidatura` cobra no caminho normal.

2. **Avaliação única.** A avaliação submetida não podia mais ser editada, mas
   nada impedia ABRIR outra para a mesma banca e submeter de novo — trocando
   nota e feedback em silêncio, sem que ninguém soubesse que a primeira versão
   deixou de valer.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.avaliacao.create_avaliacao import (
    CreateAvaliacaoRequest,
    CreateAvaliacaoUseCase,
)
from src.use_cases.solicitacao_troca.create_solicitacao_troca import (
    CreateSolicitacaoTrocaUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


class FakeCandidaturaRepo:
    def __init__(self, usuarios=()):
        self._usuarios = list(usuarios)

    def get_by_banca(self, banca_id):
        return [SimpleNamespace(usuario_id=u, banca_id=banca_id) for u in self._usuarios]


class FakeEquipeProjetoRepo:
    """A legada, vazia — é o estado real de toda banca marcada pelo cronograma."""

    def get_by_banca(self, banca_id):
        return []


class FakeBancaEscopoRepo:
    def get_escopo_ids(self, banca_id):
        return [10]


class FakeProjetoEscopoRepo:
    def get_by_id(self, escopo_id):
        return SimpleNamespace(projeto_id=7)


class FakeProjetoMembroRepo:
    def __init__(self, membros):
        self._membros = list(membros)

    def get_by_projeto(self, projeto_id, apenas_atuais=False):
        return [SimpleNamespace(usuario_id=u) for u in self._membros]


def montar_troca(*, candidatos=(), equipe=()):
    uc = CreateSolicitacaoTrocaUseCase.__new__(CreateSolicitacaoTrocaUseCase)
    uc.candidatura_repository = FakeCandidaturaRepo(candidatos)
    uc.equipe_projeto_repository = FakeEquipeProjetoRepo()
    uc.banca_escopo_repository = FakeBancaEscopoRepo()
    uc.escopo_repository = FakeProjetoEscopoRepo()
    uc.membro_repository = FakeProjetoMembroRepo(equipe)
    banca = SimpleNamespace(id=1, nome_projeto="QA5-A", coordenador_id=4)
    return uc, banca


class TestQuemNaoPodeAssumirAVaga:
    def test_consultor_da_equipe_do_projeto(self):
        """⭐ O caso do roteiro: a Bia é da equipe do QA5-A e foi convidada
        para avaliar a banca do QA5-A."""
        uc, banca = montar_troca(candidatos=[7], equipe=[5, 6])
        assert 5 in uc._excluidos(banca)
        assert 6 in uc._excluidos(banca)

    def test_coordenador_do_projeto(self):
        uc, banca = montar_troca(candidatos=[7], equipe=[5])
        assert 4 in uc._excluidos(banca)

    def test_quem_ja_e_candidato_da_banca(self):
        uc, banca = montar_troca(candidatos=[7], equipe=[5])
        assert 7 in uc._excluidos(banca)

    def test_quem_e_de_fora_continua_podendo(self):
        uc, banca = montar_troca(candidatos=[7], equipe=[5, 6])
        assert 23 not in uc._excluidos(banca)

    def test_a_mensagem_de_recusa_nomeia_as_duas_metades(self):
        uc, banca = montar_troca(candidatos=[7], equipe=[5])
        uc.usuario_repository = SimpleNamespace(
            get_by_id=lambda uid: SimpleNamespace(id=uid, ativo=True)
        )
        with pytest.raises(RegraDeNegocioError) as erro:
            uc._validar_convidado(banca, usuario_id=7, convidado_id=5)
        assert "grupo do projeto" in str(erro.value)


class FakeAvaliacaoRepo:
    def __init__(self, existentes=()):
        self._existentes = list(existentes)
        self.criadas = []

    def get_by_banca(self, banca_id, sessao=None):
        return [
            a
            for a in self._existentes
            if a.banca_id == banca_id and (sessao is None or a.sessao == sessao)
        ]

    def create(self, **kwargs):
        criada = SimpleNamespace(id=99, **kwargs)
        self.criadas.append(criada)
        return criada


def avaliacao(id, avaliador_id, status, sessao=1, banca_id=1):
    return SimpleNamespace(
        id=id, avaliador_id=avaliador_id, status=status, sessao=sessao, banca_id=banca_id
    )


def montar_avaliacao(existentes=()):
    uc = CreateAvaliacaoUseCase.__new__(CreateAvaliacaoUseCase)
    uc.repository = FakeAvaliacaoRepo(existentes)
    uc.banca_repository = SimpleNamespace(
        get_by_id=lambda _id: SimpleNamespace(id=1, realizado_em=None)
    )
    uc.sessao_repository = SimpleNamespace(
        get_corrente=lambda _id: SimpleNamespace(numero=1)
    )
    uc.candidatura_repository = FakeCandidaturaRepo([7, 19])
    return uc


def pedido():
    return CreateAvaliacaoRequest(banca_id=1, formulario_id=1)


class TestUmVotoPorPessoa:
    def test_nao_abre_avaliacao_nova_depois_de_ja_ter_votado(self):
        uc = montar_avaliacao([avaliacao(1, avaliador_id=7, status="submetida")])
        with pytest.raises(RegraDeNegocioError) as erro:
            uc.execute(pedido(), avaliador_id=7)
        assert "não pode ser refeita" in str(erro.value)

    def test_rascunho_duplicado_continua_permitido(self):
        """O front cria a avaliação ao ABRIR o formulário — quem abre duas
        vezes não está tentando burlar nada, e a apuração já reduz a um voto."""
        uc = montar_avaliacao([avaliacao(1, avaliador_id=7, status="rascunho")])
        assert uc.execute(pedido(), avaliador_id=7)["id"] == 99

    def test_o_voto_de_outra_pessoa_nao_bloqueia_o_meu(self):
        uc = montar_avaliacao([avaliacao(1, avaliador_id=19, status="submetida")])
        assert uc.execute(pedido(), avaliador_id=7)["id"] == 99

    def test_voto_da_sessao_anterior_nao_bloqueia_a_segunda_banca(self):
        """⭐ A 2ª banca é uma nova chance: quem reprovou a 1ª vota de novo."""
        uc = montar_avaliacao(
            [avaliacao(1, avaliador_id=7, status="submetida", sessao=1)]
        )
        uc.sessao_repository = SimpleNamespace(
            get_corrente=lambda _id: SimpleNamespace(numero=2)
        )
        assert uc.execute(pedido(), avaliador_id=7)["id"] == 99
