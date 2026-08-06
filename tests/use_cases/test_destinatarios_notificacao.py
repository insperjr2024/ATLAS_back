"""O §3 aplicado a quem RECEBE notificação.

O briefing dá três regras de visibilidade e todas as três podem vazar por
notificação — um alerta que chega a quem não pode abrir a página do projeto
conta o que o §3 mandava esconder:

    Gerente ...... só a própria frente, mais os sinérgicos que a incluam
    Diretor ...... todas as frentes
    Coord/cons ... só onde estão alocados

Estes testes prendem as três. Os dublês são escritos à mão, no idioma do repo.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.notificacao import destinatarios


def usuario(id, posicao, ativo=True):
    return SimpleNamespace(id=id, posicao=posicao, ativo=ativo, nome=f"u{id}")


def membro(usuario_id, papel="consultor"):
    return SimpleNamespace(usuario_id=usuario_id, papel=papel)


class BancoFake:
    """Substitui os 5 repositórios de uma vez.

    `destinatarios.py` instancia os repositórios dentro das funções, então o
    teste troca as CLASSES no módulo (via `monkeypatch`) em vez de injetar —
    ver `_montar` abaixo.
    """

    def __init__(self, *, frentes_do_projeto, usuarios, frentes_por_usuario, membros, candidaturas=()):
        self.frentes_do_projeto = frentes_do_projeto
        self.usuarios = usuarios
        self.frentes_por_usuario = frentes_por_usuario
        self.membros = membros
        self.candidaturas = candidaturas


@pytest.fixture
def montar(monkeypatch):
    def _montar(banco: BancoFake):
        class ProjetoFrenteFake:
            def __init__(self, db): pass
            def get_by_projeto(self, projeto_id):
                return [SimpleNamespace(frente_id=f) for f in banco.frentes_do_projeto]

        class UsuarioFake:
            def __init__(self, db): pass
            def get_por_posicao(self, posicao):
                return [u for u in banco.usuarios if u.posicao == posicao]

        class UsuarioFrenteFake:
            def __init__(self, db): pass
            def get_by_usuario(self, usuario_id):
                return [
                    SimpleNamespace(frente_id=f)
                    for f in banco.frentes_por_usuario.get(usuario_id, [])
                ]

        class ProjetoMembroFake:
            def __init__(self, db): pass
            def get_by_projeto(self, projeto_id, apenas_atuais=False):
                return banco.membros

        class CandidaturaFake:
            def __init__(self, db): pass
            def get_by_banca(self, banca_id):
                return [SimpleNamespace(usuario_id=u) for u in banco.candidaturas]

        monkeypatch.setattr(destinatarios, "ProjetoFrenteRepository", ProjetoFrenteFake)
        monkeypatch.setattr(destinatarios, "UsuarioRepository", UsuarioFake)
        monkeypatch.setattr(destinatarios, "UsuarioFrenteRepository", UsuarioFrenteFake)
        monkeypatch.setattr(destinatarios, "ProjetoMembroRepository", ProjetoMembroFake)
        monkeypatch.setattr(destinatarios, "CandidaturaRepository", CandidaturaFake)

    return _montar


# Frentes: 1 = Business, 2 = Tech, 3 = Direito.
DIRETORA = usuario(1, "diretor")
GERENTE_BUSINESS = usuario(2, "gerente")
GERENTE_TECH = usuario(3, "gerente")
GERENTE_DIREITO = usuario(4, "gerente")
TODOS = [DIRETORA, GERENTE_BUSINESS, GERENTE_TECH, GERENTE_DIREITO]
VINCULOS = {2: [1], 3: [2], 4: [3]}


class TestGerente:
    def test_so_o_gerente_da_frente_do_projeto(self, montar):
        """A regra que mais vaza se esquecida: notificar todos os gerentes
        contaria a cada um o que acontece na frente dos outros."""
        montar(BancoFake(
            frentes_do_projeto=[1], usuarios=TODOS,
            frentes_por_usuario=VINCULOS, membros=[],
        ))
        recebem = destinatarios.lideranca_do_projeto(None, projeto_id=1)
        assert GERENTE_BUSINESS.id in recebem
        assert GERENTE_TECH.id not in recebem
        assert GERENTE_DIREITO.id not in recebem

    def test_projeto_sinergico_avisa_os_dois_gerentes(self, montar):
        """§2: "deve aparecer para os gerentes das duas frentes envolvidas"."""
        montar(BancoFake(
            frentes_do_projeto=[1, 2], usuarios=TODOS,
            frentes_por_usuario=VINCULOS, membros=[],
        ))
        recebem = destinatarios.lideranca_do_projeto(None, projeto_id=1)
        assert {GERENTE_BUSINESS.id, GERENTE_TECH.id} <= set(recebem)
        assert GERENTE_DIREITO.id not in recebem

    def test_gerente_desativado_nao_recebe(self, montar):
        """§10: quem saiu perde o acesso — e com ele a notificação."""
        montar(BancoFake(
            frentes_do_projeto=[1],
            usuarios=[DIRETORA, usuario(2, "gerente", ativo=False)],
            frentes_por_usuario=VINCULOS, membros=[],
        ))
        assert 2 not in destinatarios.lideranca_do_projeto(None, projeto_id=1)


class TestDiretor:
    def test_recebe_de_qualquer_frente(self, montar):
        for frente in ([1], [2], [3]):
            montar(BancoFake(
                frentes_do_projeto=frente, usuarios=TODOS,
                frentes_por_usuario=VINCULOS, membros=[],
            ))
            assert DIRETORA.id in destinatarios.lideranca_do_projeto(None, projeto_id=1)

    def test_nao_duplica_quem_e_diretor_e_gerente(self, montar):
        montar(BancoFake(
            frentes_do_projeto=[1],
            usuarios=[DIRETORA, GERENTE_BUSINESS],
            frentes_por_usuario={1: [1], 2: [1]}, membros=[],
        ))
        recebem = destinatarios.lideranca_do_projeto(None, projeto_id=1)
        assert len(recebem) == len(set(recebem))


class TestEquipe:
    def test_so_quem_esta_alocado_hoje(self, montar):
        montar(BancoFake(
            frentes_do_projeto=[1], usuarios=TODOS, frentes_por_usuario=VINCULOS,
            membros=[membro(10, "coordenador"), membro(11), membro(12)],
        ))
        assert destinatarios.equipe_do_projeto(None, projeto_id=1) == [10, 11, 12]

    def test_todos_do_projeto_e_equipe_mais_lideranca_sem_repetir(self, montar):
        montar(BancoFake(
            frentes_do_projeto=[1], usuarios=TODOS, frentes_por_usuario=VINCULOS,
            # A diretora também coordena este projeto — não pode entrar duas vezes.
            membros=[membro(DIRETORA.id, "coordenador"), membro(11)],
        ))
        recebem = destinatarios.todos_do_projeto(None, projeto_id=1)
        assert len(recebem) == len(set(recebem))
        assert {DIRETORA.id, 11, GERENTE_BUSINESS.id} <= set(recebem)
        assert GERENTE_TECH.id not in recebem


class TestInscritosNaBanca:
    def test_inscritos_recebem_mesmo_sendo_de_fora(self, montar):
        """A exceção documentada: §8 proíbe a equipe de se inscrever na própria
        banca, então quem se inscreveu é sempre de fora do projeto. Remarcar
        sem avisar essas pessoas as deixaria com a agenda presa numa data que
        não vale mais."""
        montar(BancoFake(
            frentes_do_projeto=[1], usuarios=TODOS, frentes_por_usuario=VINCULOS,
            membros=[membro(10, "coordenador")], candidaturas=[20, 21],
        ))
        assert destinatarios.inscritos_na_banca(None, banca_id=1) == [20, 21]
