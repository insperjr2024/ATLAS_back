"""§8 — piso POR frente e liderança da frente, separado do piso total.

Ver `src/utils/composicao_banca.py`. Segue o mesmo padrão de
`tests/use_cases/test_capacidade.py`: `Cls.__new__(Cls)` + repositórios fake
por cima, sem precisar de sessão de banco real.
"""

from types import SimpleNamespace

from src.utils.composicao_banca import ComposicaoBancaChecker


def usuario(id, posicao="consultor"):
    return SimpleNamespace(id=id, posicao=posicao)


class FakeUsuarioFrenteRepo:
    def __init__(self, por_frente: dict):
        self._por_frente = por_frente

    def get_by_frente(self, frente_id):
        return [SimpleNamespace(usuario_id=uid) for uid in self._por_frente.get(frente_id, [])]


class FakeUsuarioRepo:
    def __init__(self, usuarios: list):
        self._usuarios = usuarios

    def get_all(self):
        return self._usuarios


class FakeEquipeProjetoRepo:
    def __init__(self, ids=()):
        self._ids = ids

    def get_by_banca(self, banca_id):
        return [SimpleNamespace(usuario_id=uid) for uid in self._ids]


def frente(id, nome, piso_banca):
    return SimpleNamespace(id=id, nome=nome, piso_banca=piso_banca)


def montar(por_frente, usuarios, equipe_projeto_ids=(), coordenador_id=None):
    checker = ComposicaoBancaChecker.__new__(ComposicaoBancaChecker)
    checker.usuario_frente_repository = FakeUsuarioFrenteRepo(por_frente)
    checker.usuario_repository = FakeUsuarioRepo(usuarios)
    checker.equipe_projeto_repository = FakeEquipeProjetoRepo(equipe_projeto_ids)
    banca = SimpleNamespace(id=1, coordenador_id=coordenador_id)
    return checker, banca


class TestPisoPorFrente:
    def test_total_suficiente_mas_todo_de_uma_frente_ainda_falta_a_outra(self):
        """O caso que o piso TOTAL sozinho não pega: banca Business(3)+Tech(2)
        fechada com 5 pessoas, todas de Business — Tech continua descoberto."""
        por_frente = {1: [10, 11, 12, 13, 14], 2: []}
        usuarios = [usuario(i) for i in range(10, 15)]
        checker, banca = montar(por_frente, usuarios)
        frentes = [frente(1, "Business", 3), frente(2, "Tech", 2)]

        status = checker.verificar(banca, frentes, {10, 11, 12, 13, 14}, lideranca_minima_por_frente=0)

        assert not status.ok
        deficit_tech = next(d for d in status.deficits if d.frente_id == 2)
        assert deficit_tech.piso_faltando == 2

    def test_cada_frente_com_seu_proprio_piso_fecha_sem_deficit(self):
        por_frente = {1: [10, 11, 12], 2: [20, 21]}
        usuarios = [usuario(i) for i in (10, 11, 12, 20, 21)]
        checker, banca = montar(por_frente, usuarios)
        frentes = [frente(1, "Business", 3), frente(2, "Tech", 2)]

        status = checker.verificar(
            banca, frentes, {10, 11, 12, 20, 21}, lideranca_minima_por_frente=0
        )

        assert status.ok


class TestLideranca:
    def test_sem_gerente_nem_diretor_falta_lideranca(self):
        por_frente = {1: [10, 11, 12]}
        usuarios = [usuario(i) for i in (10, 11, 12)]
        checker, banca = montar(por_frente, usuarios)
        frentes = [frente(1, "Business", 3)]

        status = checker.verificar(banca, frentes, {10, 11, 12}, lideranca_minima_por_frente=1)

        assert not status.ok
        assert status.deficits[0].lideranca_faltando == 1
        # Piso já bateu (3 de Business) — só a liderança falta.
        assert status.deficits[0].piso_faltando == 0

    def test_gerente_da_frente_cobre_piso_e_lideranca_ao_mesmo_tempo(self):
        por_frente = {1: [10, 11, 12]}
        usuarios = [usuario(10, "gerente"), usuario(11), usuario(12)]
        checker, banca = montar(por_frente, usuarios)
        frentes = [frente(1, "Business", 3)]

        status = checker.verificar(banca, frentes, {10, 11, 12}, lideranca_minima_por_frente=1)

        assert status.ok

    def test_diretor_cobre_lideranca_de_qualquer_frente(self):
        por_frente = {1: [11, 12], 2: [21, 22]}
        usuarios = [usuario(11), usuario(12), usuario(21), usuario(22), usuario(99, "diretor_projetos")]
        checker, banca = montar(por_frente, usuarios)
        frentes = [frente(1, "Business", 2), frente(2, "Tech", 2)]

        status = checker.verificar(
            banca, frentes, {11, 12, 21, 22, 99}, lideranca_minima_por_frente=1
        )

        assert status.ok

    def test_coordenador_do_proprio_projeto_nao_conta_mesmo_sendo_gerente(self):
        """Alguém pode ser gerente de outra frente e AINDA ASSIM estar
        coordenando este projeto — a posição global não muda quem ele é
        DENTRO deste projeto, e a equipe do próprio projeto nunca conta pra
        liderança da própria banca (nem pode se candidatar a ela)."""
        por_frente = {1: [10, 11, 12]}
        usuarios = [usuario(10, "gerente"), usuario(11), usuario(12)]
        checker, banca = montar(por_frente, usuarios, coordenador_id=10)
        frentes = [frente(1, "Business", 3)]

        status = checker.verificar(banca, frentes, {10, 11, 12}, lideranca_minima_por_frente=1)

        assert not status.ok
        assert status.deficits[0].lideranca_faltando == 1

    def test_membro_da_equipe_do_projeto_tambem_nao_conta(self):
        por_frente = {1: [10, 11, 12]}
        usuarios = [usuario(10, "gerente"), usuario(11), usuario(12)]
        checker, banca = montar(por_frente, usuarios, equipe_projeto_ids=[10])
        frentes = [frente(1, "Business", 3)]

        status = checker.verificar(banca, frentes, {10, 11, 12}, lideranca_minima_por_frente=1)

        assert not status.ok
        assert status.deficits[0].lideranca_faltando == 1
