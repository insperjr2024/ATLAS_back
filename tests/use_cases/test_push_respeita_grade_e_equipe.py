"""§8 e §11 — as duas exclusões do push que a Rodada 5 do roteiro pegou erradas.

1. **Grade horária.** `banca.data_hora` é gravado em UTC (o front manda
   `toISOString()`) e a grade é preenchida em horário de aula. Comparados crus,
   a checagem errava por 3 horas e fazia o OPOSTO do que promete: escalava quem
   tinha aula na hora da banca e poupava quem estava livre.

2. **Equipe do projeto.** O conjunto de excluídos lia só a legada
   `equipe_projeto`, vazia para banca marcada pelo cronograma. Só o coordenador
   estava protegido de verdade (é coluna da banca); os CONSULTORES do projeto
   podiam ser escalados para avaliar o próprio trabalho.

Mesmo padrão de fake do `test_push_composicao_por_frente.py`.
"""

from datetime import datetime, time
from types import SimpleNamespace

from src.use_cases.banca.push_alocacao_automatica import PushAlocacaoAutomaticaUseCase


class FakeGradeHorariaRepo:
    def __init__(self, faixas=()):
        self._faixas = list(faixas)

    def get_por_semestre(self, semestre_id):
        return self._faixas


class FakeSemestreRepo:
    def get_por_data(self, data):
        return SimpleNamespace(id=1)


class FakeBancaEscopoRepo:
    def __init__(self, escopo_ids=()):
        self._escopo_ids = list(escopo_ids)

    def get_escopo_ids(self, banca_id):
        return self._escopo_ids


class FakeProjetoEscopoRepo:
    def __init__(self, por_id):
        self._por_id = por_id

    def get_by_id(self, escopo_id):
        return self._por_id.get(escopo_id)


class FakeProjetoMembroRepo:
    def __init__(self, por_projeto):
        self._por_projeto = por_projeto

    def get_by_projeto(self, projeto_id, apenas_atuais=False):
        return self._por_projeto.get(projeto_id, [])


class FakeEquipeProjetoRepo:
    def get_by_banca(self, banca_id):
        return []


def faixa(usuario_id, dia_semana, inicio, fim):
    return SimpleNamespace(
        usuario_id=usuario_id,
        dia_semana=dia_semana,
        hora_inicio=time.fromisoformat(inicio),
        hora_fim=time.fromisoformat(fim),
    )


class FakeVendedorRepo:
    """Nenhum vendedor, salvo quando o teste passar um mapa.

    Existe desde que o §8 passou a barrar também quem VENDEU o projeto — antes,
    `membros_da_banca` não consultava esta fonte.
    """

    def __init__(self, por_projeto=None):
        self._por_projeto = por_projeto or {}

    def get_by_projeto(self, projeto_id):
        from types import SimpleNamespace
        return [
            SimpleNamespace(usuario_id=u, projeto_id=projeto_id)
            for u in self._por_projeto.get(projeto_id, [])
        ]


def montar(*, data_hora, faixas=(), escopo_ids=(), membros_por_projeto=None):
    uc = PushAlocacaoAutomaticaUseCase.__new__(PushAlocacaoAutomaticaUseCase)
    uc.grade_horaria_repository = FakeGradeHorariaRepo(faixas)
    uc.semestre_repository = FakeSemestreRepo()
    uc.equipe_projeto_repository = FakeEquipeProjetoRepo()
    uc.vendedor_repository = FakeVendedorRepo()
    uc.banca_escopo_repository = FakeBancaEscopoRepo(escopo_ids)
    uc.escopo_repository = FakeProjetoEscopoRepo(
        {eid: SimpleNamespace(projeto_id=7) for eid in escopo_ids}
    )
    uc.membro_repository = FakeProjetoMembroRepo(membros_por_projeto or {})
    banca = SimpleNamespace(id=1, data_hora=data_hora, coordenador_id=99)
    return uc, banca


# 20/08/2026 é uma QUINTA. 12:00Z = 09:00 em São Paulo.
BANCA_QUINTA_9H = datetime(2026, 8, 20, 12, 0)
QUINTA = 3


class TestAulaNaHoraDaBanca:
    def test_quem_tem_aula_no_horario_da_TELA_e_barrado(self):
        """A banca acontece às 09:00; a aula das 07:30–09:30 pega esse horário."""
        uc, banca = montar(
            data_hora=BANCA_QUINTA_9H,
            faixas=[faixa(1, QUINTA, "07:30", "09:30")],
        )
        assert uc._com_aula_no_horario(banca) == {1}

    def test_quem_tem_aula_no_horario_do_valor_CRU_nao_e_barrado(self):
        """A trava do teste anterior: 12:00–14:00 contém as 12:00 gravadas em
        UTC, mas a banca é às 09:00 e essa pessoa está livre nela.

        Era exatamente ao contrário antes da correção."""
        uc, banca = montar(
            data_hora=BANCA_QUINTA_9H,
            faixas=[faixa(1, QUINTA, "12:00", "14:00")],
        )
        assert uc._com_aula_no_horario(banca) == set()

    def test_aula_em_outro_dia_nao_barra(self):
        uc, banca = montar(
            data_hora=BANCA_QUINTA_9H,
            faixas=[faixa(1, 2, "07:30", "09:30")],  # quarta
        )
        assert uc._com_aula_no_horario(banca) == set()

    def test_quem_nao_preencheu_a_grade_continua_elegivel(self):
        uc, banca = montar(data_hora=BANCA_QUINTA_9H, faixas=[])
        assert uc._com_aula_no_horario(banca) == set()

    def test_banca_de_fim_de_semana_no_horario_local_nao_consulta_grade(self):
        # Sábado 21:00 em SP = domingo 00:00Z. Pelo valor cru seria domingo;
        # pelo horário local é sábado. Nos dois casos não há aula, e o que o
        # teste tranca é que a decisão sai da hora LOCAL.
        uc, banca = montar(
            data_hora=datetime(2026, 8, 23, 0, 0),
            faixas=[faixa(1, 5, "19:00", "23:00")],
        )
        assert uc._com_aula_no_horario(banca) == set()


class TestEquipeDoProjetoNaoAvaliaOProprioTrabalho:
    def test_consultor_do_projeto_e_excluido_do_rodizio(self):
        """A banca cobre o escopo 10, do projeto 7, cuja equipe é 5 e 6.

        Antes, com `equipe_projeto` vazia (é o caso de toda banca marcada pelo
        cronograma), os dois entravam no sorteio da própria banca."""
        uc, banca = montar(
            data_hora=BANCA_QUINTA_9H,
            escopo_ids=[10],
            membros_por_projeto={
                7: [SimpleNamespace(usuario_id=5), SimpleNamespace(usuario_id=6)]
            },
        )
        excluidos = uc._excluidos(banca, candidaturas_atuais=[])
        assert {5, 6} <= excluidos

    def test_coordenador_continua_excluido(self):
        uc, banca = montar(data_hora=BANCA_QUINTA_9H)
        assert 99 in uc._excluidos(banca, candidaturas_atuais=[])

    def test_quem_ja_esta_alocado_nao_entra_de_novo(self):
        uc, banca = montar(data_hora=BANCA_QUINTA_9H)
        excluidos = uc._excluidos(
            banca, candidaturas_atuais=[SimpleNamespace(usuario_id=42)]
        )
        assert 42 in excluidos

    def test_quem_e_de_fora_do_projeto_continua_elegivel(self):
        uc, banca = montar(
            data_hora=BANCA_QUINTA_9H,
            escopo_ids=[10],
            membros_por_projeto={7: [SimpleNamespace(usuario_id=5)]},
        )
        assert 8 not in uc._excluidos(banca, candidaturas_atuais=[])
