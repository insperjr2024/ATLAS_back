"""§8 — a composição exigida por frente, contra a regra da COMBINAÇÃO.

Ver `src/utils/composicao_banca.py`. Segue o padrão de
`tests/use_cases/test_capacidade.py`: `Cls.__new__(Cls)` + repositórios fake
por cima, sem sessão de banco.

O que estes testes protegem, depois da virada de 2026-09-01:

- **Liderança é vaga A MAIS.** Business com 3 pessoas, uma delas gerente, não
  fecha mais: são 3 membros E 1 liderança, quatro pessoas.
- **O diretor cobre a liderança de qualquer frente**, inclusive de uma a que
  não está vinculado — e por isso não consome vaga de membro dela.
- **Os tetos**, que não existiam antes desta mudança.
- **A equipe do próprio projeto não conta**, nem como membro nem como líder.
"""

from types import SimpleNamespace

from src.utils.composicao_banca import ComposicaoBancaChecker


def usuario(id, posicao="consultor"):
    return SimpleNamespace(id=id, posicao=posicao)


def regra(frente_id, nome, min_membros=1, max_membros=99, min_lideranca=1, max_lideranca=99):
    """Uma `RegraDaFrente` já resolvida — é o que o checker recebe."""
    return SimpleNamespace(
        frente_id=frente_id, frente_nome=nome,
        min_membros=min_membros, max_membros=max_membros,
        min_lideranca=min_lideranca, max_lideranca=max_lideranca,
    )


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


def montar(por_frente, usuarios, equipe_projeto_ids=(), coordenador_id=None):
    checker = ComposicaoBancaChecker.__new__(ComposicaoBancaChecker)
    checker.usuario_frente_repository = FakeUsuarioFrenteRepo(por_frente)
    checker.usuario_repository = FakeUsuarioRepo(usuarios)
    checker.equipe_projeto_repository = FakeEquipeProjetoRepo(equipe_projeto_ids)
    banca = SimpleNamespace(id=1, coordenador_id=coordenador_id)
    return checker, banca


BUSINESS, TECH = 1, 2


class TestLiderancaEhVagaAMais:
    def test_tres_de_business_com_um_gerente_nao_fecha(self):
        """⭐ A virada. Antes fechava: o gerente contava entre os 3."""
        por_frente = {BUSINESS: [10, 11, 12]}
        usuarios = [usuario(10, "gerente"), usuario(11), usuario(12)]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12}
        )

        assert not status.ok
        assert status.deficits[0].piso_faltando == 1

    def test_quatro_de_business_com_um_gerente_fecha(self):
        por_frente = {BUSINESS: [10, 11, 12, 13]}
        usuarios = [usuario(10, "gerente")] + [usuario(i) for i in (11, 12, 13)]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12, 13}
        )

        assert status.ok

    def test_o_segundo_gerente_volta_a_contar_como_membro(self):
        """A cota de liderança é 1: o gerente que sobra é gente da frente
        como qualquer outra, senão dois gerentes valeriam menos que um."""
        por_frente = {BUSINESS: [10, 11, 12]}
        usuarios = [usuario(10, "gerente"), usuario(11, "gerente"), usuario(12)]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca, [regra(BUSINESS, "Business", min_membros=2)], {10, 11, 12}
        )

        assert status.ok


class TestODiretor:
    def test_diretor_cobre_a_lideranca_sem_ser_da_frente(self):
        """Ele enxerga todas (§3). E, por não estar vinculado a Business, não
        tira ninguém da conta de membros dela."""
        por_frente = {BUSINESS: [10, 11, 12]}
        usuarios = [usuario(i) for i in (10, 11, 12)] + [usuario(99, "diretor_projetos")]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12, 99}
        )

        assert status.ok

    def test_um_diretor_cobre_as_duas_frentes(self):
        por_frente = {BUSINESS: [10, 11, 12], TECH: [20, 21]}
        usuarios = [usuario(i) for i in (10, 11, 12, 20, 21)] + [usuario(99, "diretor")]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca,
            [regra(BUSINESS, "Business", min_membros=3), regra(TECH, "Tech", min_membros=2)],
            {10, 11, 12, 20, 21, 99},
        )

        assert status.ok


class TestPisoPorFrente:
    def test_total_suficiente_mas_todo_de_uma_frente_nao_fecha(self):
        """O caso que o piso TOTAL sozinho não pega: Business(3)+Tech(2) com 5
        pessoas, todas de Business — Tech continua descoberto."""
        por_frente = {BUSINESS: [10, 11, 12, 13, 14], TECH: []}
        usuarios = [usuario(i) for i in range(10, 15)]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca,
            [regra(BUSINESS, "Business", min_membros=3), regra(TECH, "Tech", min_membros=2)],
            set(range(10, 15)),
        )

        tech = next(d for d in status.deficits if d.frente_id == TECH)
        assert tech.piso_faltando == 2
        assert tech.lideranca_faltando == 1


class TestOsTetos:
    def test_membros_alem_do_teto_acusa(self):
        """Novo em 2026-09-01: segura a banca que encheu de uma frente só."""
        por_frente = {BUSINESS: [10, 11, 12, 13, 14]}
        usuarios = [usuario(10, "gerente")] + [usuario(i) for i in (11, 12, 13, 14)]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca,
            [regra(BUSINESS, "Business", min_membros=2, max_membros=3)],
            {10, 11, 12, 13, 14},
        )

        assert not status.ok
        assert status.deficits[0].membros_sobrando == 1
        assert status.teto_ok is False

    def test_lideranca_alem_do_teto_acusa(self):
        """A banca é para avaliar, não para reunir a gestão inteira."""
        por_frente = {BUSINESS: [10, 11, 12, 13]}
        usuarios = [usuario(10, "gerente"), usuario(11, "gerente")] + [
            usuario(i) for i in (12, 13)
        ]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca,
            [regra(BUSINESS, "Business", min_membros=1, max_lideranca=1)],
            {10, 11, 12, 13},
        )

        assert status.deficits[0].lideranca_sobrando == 1

    def test_dentro_do_teto_passa(self):
        por_frente = {BUSINESS: [10, 11, 12]}
        usuarios = [usuario(10, "gerente"), usuario(11), usuario(12)]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca,
            [regra(BUSINESS, "Business", min_membros=2, max_membros=3, max_lideranca=1)],
            {10, 11, 12},
        )

        assert status.ok


class TestAEquipeDoProjeto:
    def test_o_gerente_da_equipe_nao_cobre_a_lideranca(self):
        """Ele já não pode se candidatar à própria banca; aqui é a mesma
        exclusão, agora também na contagem."""
        por_frente = {BUSINESS: [10, 11, 12, 13]}
        usuarios = [usuario(10, "gerente")] + [usuario(i) for i in (11, 12, 13)]
        checker, banca = montar(por_frente, usuarios, equipe_projeto_ids=(10,))

        status = checker.verificar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12, 13}
        )

        assert status.deficits[0].lideranca_faltando == 1

    def test_o_coordenador_do_projeto_tambem_e_excluido(self):
        por_frente = {BUSINESS: [10, 11, 12, 13]}
        usuarios = [usuario(10, "gerente")] + [usuario(i) for i in (11, 12, 13)]
        checker, banca = montar(por_frente, usuarios, coordenador_id=10)

        status = checker.verificar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12, 13}
        )

        assert status.deficits[0].lideranca_faltando == 1


class TestOBlend:
    def test_business_mais_direito_fecha_com_seis(self):
        """O exemplo do usuário: 3 de Business + 1 de Direito + 1 liderança de
        cada = 6."""
        DIREITO = 3
        por_frente = {BUSINESS: [10, 11, 12, 13], DIREITO: [20, 21]}
        usuarios = [usuario(10, "gerente"), usuario(20, "gerente")] + [
            usuario(i) for i in (11, 12, 13, 21)
        ]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca,
            [regra(BUSINESS, "Business", min_membros=3), regra(DIREITO, "Direito", min_membros=1)],
            {10, 11, 12, 13, 20, 21},
        )

        assert status.ok
