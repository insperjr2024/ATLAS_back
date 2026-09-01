"""⭐ A faixa que pinta a JANELA de cada escopo no cronograma (§5, §7).

⚠ **Esta faixa mudou de significado.** Antes ela ia da reunião inicial até a
*data da banca*, e por isso sumia enquanto a banca não tivesse data — justo
quando ela é mais útil, que é na hora de decidir onde a banca cabe.

Agora ela é a janela: da reunião inicial até *vendidos + ajustados* dias úteis
depois dela. É **previsão**, não consequência — a banca precisa caber dentro
dela (§9), não o contrário.

Ela continua DERIVADA a cada leitura: mover a reunião inicial ou aprovar dias
de ajuste redesenha o retângulo sozinho, e é essa propriedade que estes testes
prendem.

`_faixas_derivadas` não toca em `self`, então a instância vem sem `__init__` —
mesma manha de `test_marco_sem_tarefa.py`.
"""

from datetime import date
from types import SimpleNamespace

from src.use_cases.cronograma.get_cronograma import GetCronogramaUseCase

CASO = GetCronogramaUseCase.__new__(GetCronogramaUseCase)

SEG_10_08 = date(2026, 8, 10)
#: 10 dias úteis a partir de 10/08 (sem feriado no meio) fecham em 21/08.
SEX_21_08 = date(2026, 8, 21)
#: Com +5 ajustados, vão até 28/08.
SEX_28_08 = date(2026, 8, 28)


def projeto(kickoff=None, dias_ambientacao=0, inicio_ambientacao=None):
    return SimpleNamespace(
        data_kickoff=kickoff,
        dias_ambientacao=dias_ambientacao,
        data_inicio_ambientacao=inicio_ambientacao,
    )


def escopo(id=1, inicio=SEG_10_08, entrega_real=None, vendidos=10, ajustados=0,
           frente_id=1, calendario=None):
    return SimpleNamespace(
        id=id,
        # A frente e o rótulo formam o calendário base do escopo (§5.4).
        frente_id=frente_id,
        calendario=calendario,
        data_inicio=inicio,
        data_entrega_real=entrega_real,
        # Só `_janela` lê esta: é uma das datas que abrem o intervalo de meses
        # que a aba desenha.
        data_entrega_planejada=None,
        dias_uteis_vendidos=vendidos,
        dias_uteis_ajustados=ajustados,
    )


def janelas(escopos, calendario=()):
    faixas = CASO._faixas_derivadas(projeto(), escopos, list(calendario))
    return [f for f in faixas if f["tipo"] == "escopo"]


def dia_de_frente(data, frente_id=1):
    """Um dia não letivo de CURSO — semana de avaliação, recesso, aula cancelada.

    O que separa os dois calendários é só `frente_id`: nulo vale para todas as
    frentes (feriado), preenchido é do curso.
    """
    return SimpleNamespace(data=data, tipo="prova", descricao=None, frente_id=frente_id)


def _faixas_do_execute(monkeypatch, escopos, calendario, projeto_=None):
    """`GetCronogramaUseCase.execute` com todos os repositórios em stub.

    Não há banco nos testes desta base, e a faixa que interessa é montada em
    `execute` — é lá que os dois calendários são separados. Os repositórios
    entram vazios; só o de dia não letivo e o de escopo carregam dado.
    """
    from src.use_cases.cronograma import get_cronograma as mod

    alvo = projeto_ or projeto()
    alvo.id = 1
    alvo.calendario = None

    caso = GetCronogramaUseCase.__new__(GetCronogramaUseCase)
    caso.db = None
    caso.projeto_repository = SimpleNamespace(get_by_id=lambda _id: alvo)
    caso.escopo_repository = SimpleNamespace(get_by_projeto=lambda _id: escopos)
    caso.etapa_repository = SimpleNamespace(get_by_escopos=lambda _ids: [])
    caso.marco_repository = SimpleNamespace(get_by_projeto=lambda _id: [])
    caso.banca_repository = SimpleNamespace(get_by_projeto_escopos=lambda _ids: [])
    caso.reuniao_repository = SimpleNamespace(get_by_projeto=lambda _id: [])
    caso.historico_repository = SimpleNamespace(get_by_projeto=lambda _id: [])
    caso.semestre_repository = SimpleNamespace(get_ativo=lambda: None)
    caso.frente_repository = SimpleNamespace(get_all=lambda: [])
    caso.dia_nao_letivo_repository = SimpleNamespace(
        get_por_intervalo=lambda _i, _f: list(calendario)
    )
    # Os escopos serializados vêm de outro use case, com banco próprio; a faixa
    # não depende deles.
    monkeypatch.setattr(
        mod, "ListEscoposProjetoUseCase", lambda _db: SimpleNamespace(
            execute=lambda _pid, _ref: []
        )
    )
    return caso.execute(1, referencia=SEG_10_08)["faixas_derivadas"]


class TestJanelaDoEscopo:
    def test_da_reuniao_inicial_ate_o_fim_dos_dias_vendidos(self):
        (faixa,) = janelas([escopo()])

        assert (faixa["inicio"], faixa["fim"]) == (SEG_10_08, SEX_21_08)
        assert faixa["projeto_escopo_id"] == 1

    def test_dias_ajustados_esticam_a_faixa(self):
        """⭐ Aprovar +5 redesenha o retângulo — sem ninguém regravar nada."""
        (faixa,) = janelas([escopo(ajustados=5)])

        assert faixa["fim"] == SEX_28_08

    def test_o_rotulo_mostra_vendidos_e_ajustados_separados(self):
        """A tela nunca diz "15 vendidos": diz 10 vendidos + 5 ajustados."""
        (faixa,) = janelas([escopo(ajustados=5)])

        assert faixa["rotulo"] == "Janela do escopo (10 vendidos + 5 ajustados)"

    def test_sem_ajuste_o_rotulo_nao_polui(self):
        (faixa,) = janelas([escopo()])

        assert faixa["rotulo"] == "Janela do escopo (10 vendidos)"

    def test_sem_reuniao_inicial_nao_ha_janela(self):
        """§20.4: escopo não iniciado não tem janela — é o "0/12" da tabela."""
        assert janelas([escopo(inicio=None)]) == []

    def test_a_faixa_existe_mesmo_sem_banca_marcada(self):
        """⭐ A regressão que motivou a mudança: a janela é previsão e não
        depende da banca. Antes, escopo sem banca não tinha faixa nenhuma."""
        assert len(janelas([escopo()])) == 1

    def test_feriado_no_meio_empurra_o_fim_da_janela(self):
        """A janela é contada em dias ÚTEIS, como todo o resto do sistema."""
        (faixa,) = janelas([escopo()], calendario=[date(2026, 8, 12)])

        assert faixa["fim"] == date(2026, 8, 24)

    def test_escopos_em_paralelo_geram_duas_faixas(self):
        """§5.4 admite escopos simultâneos — cada um com a sua janela."""
        faixas = janelas([escopo(id=1), escopo(id=2, inicio=date(2026, 8, 17), vendidos=5)])

        assert [(f["projeto_escopo_id"], f["inicio"], f["fim"]) for f in faixas] == [
            (1, SEG_10_08, SEX_21_08),
            (2, date(2026, 8, 17), date(2026, 8, 21)),
        ]

    def test_escopo_entregue_mantem_a_faixa(self):
        """A janela continua no calendário depois da entrega — é o histórico do
        que foi prometido, não um estado atual."""
        assert len(janelas([escopo(entrega_real=SEX_21_08)])) == 1


class TestCalendarioDeCursoNaJanela:
    """⭐ A regressão do calendário: semana de avaliação e recesso entram na janela.

    Semana de avaliação e recesso são do CURSO — nascem com `frente_id`
    preenchido (`calendario_pdf.CATEGORIAS` marca as duas como escopo
    "frente"). Feriado é o único que vem global.

    `execute` passava para cá **só os globais**, e o efeito era a faixa do
    escopo fechando antes da hora: um escopo que atravessa a semana de provas
    consumia como trabalhados justamente os dias em que ninguém trabalha. Pior,
    era o mesmo payload se contradizendo — `escopos[].fim_janela_prevista`, de
    `ListEscoposProjetoUseCase`, sempre contou o calendário inteiro, então a
    faixa desenhada terminava dias antes do número escrito ao lado dela.

    A ambientação continua com o recorte global, e por isso ela ganha um teste
    próprio: as duas contas usam calendários diferentes de propósito.
    """

    #: Uma semana de avaliação de 3 dias no meio da janela de 10 dias úteis.
    SEMANA_DE_PROVAS = [date(2026, 8, 12), date(2026, 8, 13), date(2026, 8, 14)]

    def test_a_janela_do_escopo_conta_o_calendario_do_curso(self, monkeypatch):
        """⚠ O teste tem de passar por `execute`: `_faixas_derivadas` sempre
        contou o calendário que recebe, e era o CALLSITE que entregava a ela
        apenas os globais."""
        faixas = _faixas_do_execute(
            monkeypatch,
            escopos=[escopo()],
            calendario=[dia_de_frente(d) for d in self.SEMANA_DE_PROVAS],
        )
        (faixa,) = [f for f in faixas if f["tipo"] == "escopo"]

        # 21/08 sem as provas; com elas, três dias úteis à frente.
        assert faixa["fim"] == date(2026, 8, 26)

    def test_a_ambientacao_ignora_o_que_e_de_uma_frente_so(self):
        """A ambientação é do PROJETO: o calendário de uma frente não pode
        esticá-la, senão o mesmo projeto termina a ambientação em datas
        diferentes conforme o escopo que estiver selecionado na tela."""
        faixas = CASO._faixas_derivadas(
            projeto(kickoff=SEG_10_08, dias_ambientacao=5),
            [],
            self.SEMANA_DE_PROVAS,
            dias_nao_letivos_globais=[],
        )
        (ambientacao,) = [f for f in faixas if f["tipo"] == "ambientacao"]

        assert ambientacao["fim"] == date(2026, 8, 14)
