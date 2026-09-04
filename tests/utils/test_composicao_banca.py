"""§8 — a composição exigida por frente, contra a regra da COMBINAÇÃO.

Ver `src/utils/composicao_banca.py`. Segue o padrão de
`tests/use_cases/test_capacidade.py`: `Cls.__new__(Cls)` + repositórios fake
por cima, sem sessão de banco.

O que estes testes protegem, depois da virada de 2026-09-01:

- **Liderança é vaga A MAIS.** Business com 3 pessoas, uma delas gerente, não
  fecha mais: são 3 membros E 1 liderança, quatro pessoas.
- **Os tetos**, que não existiam antes desta mudança.
- **A equipe do próprio projeto não conta**, nem como membro nem como líder.

E, de 2026-09-04: **a diretoria é liderança SEM frente**, como o coordenador
de vendas — não cobre mais o piso de liderança de frente nenhuma (antes
cobria a de qualquer uma, por "enxergar todas").
"""

from types import SimpleNamespace

from src.utils.composicao_banca import ComposicaoBancaChecker


def usuario(id, posicao="consultor", coordenador_vendas=False):
    return SimpleNamespace(
        id=id, posicao=posicao, coordenador_vendas=coordenador_vendas
    )


def regra(frente_id, nome, min_membros=1, min_lideranca=1):
    """Uma `RegraDaFrente` já resolvida — é o que o checker recebe. Só piso:
    não há mais teto por frente (2026-09-03)."""
    return SimpleNamespace(
        frente_id=frente_id, frente_nome=nome,
        min_membros=min_membros, min_lideranca=min_lideranca,
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


class TestOCoordenador:
    """2026-09-03: coordenador passou a cobrir a liderança DA FRENTE dele,
    como o gerente. Antes caía entre os membros."""

    def test_coordenador_cobre_a_lideranca_como_o_gerente(self):
        por_frente = {BUSINESS: [10, 11, 12, 13]}
        usuarios = [usuario(10, "coordenador")] + [usuario(i) for i in (11, 12, 13)]
        checker, banca = montar(por_frente, usuarios)

        (business,) = checker.contar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12, 13}
        )

        # 10 cobre a liderança e sai da conta de membros: 3 membros + 1 líder.
        assert (business.membros, business.liderancas) == (3, 1)

    def test_tres_de_business_com_um_coordenador_nao_fecha(self):
        """Espelha o caso do gerente: liderança é vaga a mais."""
        por_frente = {BUSINESS: [10, 11, 12]}
        usuarios = [usuario(10, "coordenador"), usuario(11), usuario(12)]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12}
        )

        assert status.deficits[0].piso_faltando == 1

    def test_coordenador_so_cobre_a_lideranca_da_frente_a_que_esta_vinculado(self):
        """Diferente da diretoria: o coordenador de Tech não cobre a liderança
        de Business só por avaliar a banca dela."""
        por_frente = {BUSINESS: [11, 12], TECH: [20]}
        usuarios = [usuario(20, "coordenador"), usuario(11), usuario(12)]
        checker, banca = montar(por_frente, usuarios)

        (business,) = checker.contar(
            banca, [regra(BUSINESS, "Business", min_membros=2)], {11, 12, 20}
        )

        # 20 não é de Business: não entra na conta dela, nem como líder.
        assert (business.membros, business.liderancas) == (2, 0)


class TestOCoordenadorDeVendas:
    """2026-09-03: coordenador de vendas é liderança SEM frente — pode ir à
    banca, mas não fecha o `min_lideranca` de frente nenhuma nem entra no
    `min_membros`. Some da contagem por frente como a equipe do projeto."""

    def test_nao_cobre_a_lideranca_da_frente_a_que_esta_vinculado(self):
        por_frente = {BUSINESS: [10, 11, 12, 13]}
        usuarios = [usuario(10, "coordenador", coordenador_vendas=True)] + [
            usuario(i) for i in (11, 12, 13)
        ]
        checker, banca = montar(por_frente, usuarios)

        (business,) = checker.contar(
            banca,
            [regra(BUSINESS, "Business", min_membros=3, min_lideranca=1)],
            {10, 11, 12, 13},
        )

        # 10 sai da frente inteira: 3 membros de verdade, 0 liderança.
        assert (business.membros, business.liderancas) == (3, 0)

    def test_a_frente_com_so_o_coordenador_de_vendas_acusa_lideranca_faltando(self):
        por_frente = {BUSINESS: [10, 11, 12]}
        usuarios = [usuario(10, "coordenador", coordenador_vendas=True)] + [
            usuario(i) for i in (11, 12)
        ]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca,
            [regra(BUSINESS, "Business", min_membros=2, min_lideranca=1)],
            {10, 11, 12},
        )

        assert status.deficits[0].lideranca_faltando == 1
        # 11 e 12 fecham o piso de membros; só a liderança falta.
        assert status.deficits[0].piso_faltando == 0

    def test_coordenador_normal_ainda_cobre__so_o_de_vendas_e_que_nao(self):
        """A distinção é o `coordenador_vendas`, não a posição: coordenador
        comum de Business segue cobrindo a liderança dela."""
        por_frente = {BUSINESS: [10, 11, 12, 13]}
        usuarios = [usuario(10, "coordenador")] + [usuario(i) for i in (11, 12, 13)]
        checker, banca = montar(por_frente, usuarios)

        (business,) = checker.contar(
            banca,
            [regra(BUSINESS, "Business", min_membros=3, min_lideranca=1)],
            {10, 11, 12, 13},
        )

        assert (business.membros, business.liderancas) == (3, 1)


class TestAEquipeSaiAntesDeContar:
    def test_membro_da_equipe_que_tambem_se_candidatou_nao_e_contado(self):
        """A equipe do projeto não avalia a própria banca. Se a linha legada
        for preenchida DEPOIS da candidatura, a pessoa não pode continuar
        contando como membro."""
        por_frente = {BUSINESS: [10, 11, 12, 13]}
        usuarios = [usuario(i) for i in (10, 11, 12, 13)]
        checker, banca = montar(por_frente, usuarios, equipe_projeto_ids=(13,))

        (business,) = checker.contar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12, 13}
        )

        assert business.membros == 3


class TestODiretor:
    """2026-09-04: a diretoria virou liderança SEM frente, como o coordenador
    de vendas — não fecha mais o `min_lideranca` de frente nenhuma. Antes
    (2026-09-03) cobria a de QUALQUER uma, por "enxergar todas" (§3); isso
    saiu, a pedido."""

    def test_diretor_nao_cobre_a_lideranca_de_frente_nenhuma(self):
        """Antes fechava por "enxergar tudo" (§3). Agora não: os 3 de Business
        fecham o piso de membros, mas a liderança continua faltando."""
        por_frente = {BUSINESS: [10, 11, 12]}
        usuarios = [usuario(i) for i in (10, 11, 12)] + [usuario(99, "diretor_projetos")]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12, 99}
        )

        assert status.deficits[0].lideranca_faltando == 1
        assert status.deficits[0].piso_faltando == 0

    def test_diretor_de_qualquer_tipo_nao_cobre(self):
        """diretor_projetos, diretor_pessoas e diretor — os três, sem
        distinção — têm o mesmo tratamento."""
        por_frente = {BUSINESS: [10, 11, 12], TECH: [20, 21]}
        usuarios = (
            [usuario(i) for i in (10, 11, 12, 20, 21)]
            + [usuario(97, "diretor_projetos"), usuario(98, "diretor_pessoas"), usuario(99, "diretor")]
        )
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca,
            [regra(BUSINESS, "Business", min_membros=3), regra(TECH, "Tech", min_membros=2)],
            {10, 11, 12, 20, 21, 97, 98, 99},
        )

        # Nenhum dos três cobre a liderança de Business nem de Tech.
        assert {d.frente_nome: d.lideranca_faltando for d in status.deficits} == {
            "Business": 1,
            "Tech": 1,
        }

    def test_diretor_nao_ocupa_vaga_de_membro_por_nao_estar_na_frente(self):
        """Ele some da contagem por frente inteira — não é liderança dela nem
        membro dela, como a equipe do projeto."""
        por_frente = {BUSINESS: [10, 11, 12]}
        usuarios = [usuario(i) for i in (10, 11, 12)] + [usuario(99, "diretor")]
        checker, banca = montar(por_frente, usuarios)

        (business,) = checker.contar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12, 99}
        )

        assert (business.membros, business.liderancas) == (3, 0)


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


class TestNaoHaMaisTetoPorFrente:
    """2026-09-03: o teto por frente saiu. Encher acima do piso é "tanto faz
    a frente" — o único teto é o total da banca, conferido em
    `create_candidatura`, não aqui."""

    def test_muitos_membros_de_uma_frente_nao_acusa_nada(self):
        por_frente = {BUSINESS: [10, 11, 12, 13, 14]}
        usuarios = [usuario(10, "gerente")] + [usuario(i) for i in (11, 12, 13, 14)]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca, [regra(BUSINESS, "Business", min_membros=2)], {10, 11, 12, 13, 14}
        )

        # Piso coberto e nada mais a apontar: sem "sobrando".
        assert status.ok

    def test_varias_liderancas_nao_acusam(self):
        por_frente = {BUSINESS: [10, 11, 12, 13]}
        usuarios = [usuario(10, "gerente"), usuario(11, "gerente")] + [
            usuario(i) for i in (12, 13)
        ]
        checker, banca = montar(por_frente, usuarios)

        status = checker.verificar(
            banca, [regra(BUSINESS, "Business", min_membros=1)], {10, 11, 12, 13}
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


class TestAContagemQueATelaMostra:
    """`contar` é o que `GET /bancas` serve para a aba Bancas dizer "1 de 3
    membros". Os números precisam ser os MESMOS que a checagem usa — foi por
    isso que ela passou a se apoiar nele (2026-09-02)."""

    def test_o_gerente_da_cota_nao_aparece_entre_os_membros(self):
        por_frente = {BUSINESS: [10, 11, 12]}
        usuarios = [usuario(10, "gerente"), usuario(11), usuario(12)]
        checker, banca = montar(por_frente, usuarios)

        (business,) = checker.contar(
            banca, [regra(BUSINESS, "Business", min_membros=3)], {10, 11, 12}
        )

        assert (business.membros, business.liderancas) == (2, 1)
        assert (business.min_membros, business.min_lideranca) == (3, 1)

    def test_frente_vazia_conta_zero(self):
        por_frente = {BUSINESS: [10], TECH: []}
        checker, banca = montar(por_frente, [usuario(10)])

        contagens = checker.contar(
            banca,
            [regra(BUSINESS, "Business", min_membros=1), regra(TECH, "Tech", min_membros=2)],
            {10},
        )

        tech = next(c for c in contagens if c.frente_id == TECH)
        assert (tech.membros, tech.liderancas) == (0, 0)
