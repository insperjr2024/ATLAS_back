"""Os caminhos que ESCREVEM calendário de curso.

`test_calendario_do_projeto.py` cobre a leitura — quem enxerga o quê. Aqui
estão as três gravações que a tela dispara, e cada uma tem um jeito próprio de
dar errado em silêncio:

- carregar dias num calendário, onde `substituir` pode apagar o calendário
  vizinho por engano, já que os dois moram na mesma frente;
- renomear, que é UPDATE em três tabelas porque o rótulo é a chave — deixar
  uma para trás desliga o calendário dos escopos sem erro nenhum aparecer;
- apontar o ESCOPO para um calendário, onde um nome que não existe não casaria
  com dia algum e o escopo passaria a contar a semana de provas de ninguém.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.dia_nao_letivo_model import DiaNaoLetivoModel
from src.models.frente_model import FrenteModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_model import ProjetoModel
from src.models.semestre_model import SemestreModel
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.use_cases.dia_nao_letivo.create_dia_nao_letivo import (
    CreateDiasNaoLetivosRequest,
    CreateDiasNaoLetivosUseCase,
    DiaNaoLetivoItem,
)
from src.use_cases.dia_nao_letivo.renomear_calendario import (
    RenomearCalendarioRequest,
    RenomearCalendarioUseCase,
)
from src.use_cases.projeto_escopo.update_escopo_projeto import (
    UpdateEscopoProjetoRequest,
    UpdateEscopoProjetoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

ENGENHARIAS = "Engenharias"
COMPUTACAO = "Ciência da Computação"

PROVA_ENG = date(2026, 9, 24)
PROVA_CC = date(2026, 10, 15)

TABELAS = [
    SemestreModel.__table__,
    FrenteModel.__table__,
    ProjetoModel.__table__,
    ProjetoEscopoModel.__table__,
    DiaNaoLetivoModel.__table__,
]


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=TABELAS)
    sessao = sessionmaker(bind=engine)()
    try:
        yield sessao
    finally:
        sessao.close()


@pytest.fixture
def base(db):
    semestre = SemestreModel(
        nome="2026.2", inicio=date(2026, 7, 1), fim=date(2026, 12, 31), status="ativa"
    )
    tech = FrenteModel(nome="Tech", piso_banca=2, calendario_padrao=ENGENHARIAS)
    db.add_all([semestre, tech])
    db.flush()

    projeto = ProjetoModel(
        nome="Projeto Alfa",
        cliente="Cliente",
        criado_por=1,
        status="em_andamento",
        dias_ambientacao=5,
    )
    db.add(projeto)
    db.flush()
    escopo = ProjetoEscopoModel(
        projeto_id=projeto.id,
        frente_id=tech.id,
        nome_customizado="Escopo",
        calendario=ENGENHARIAS,
        dias_uteis_vendidos=25,
    )
    db.add(escopo)
    db.add(
        DiaNaoLetivoModel(
            semestre_id=semestre.id,
            frente_id=tech.id,
            variante=ENGENHARIAS,
            data=PROVA_ENG,
            tipo="prova",
        )
    )
    db.commit()
    return {
        "semestre": semestre.id,
        "tech": tech.id,
        "projeto": projeto.id,
        "escopo": escopo.id,
    }


def carregar(db, base, dias, variante, substituir=False):
    return CreateDiasNaoLetivosUseCase(db).execute(
        base["semestre"],
        CreateDiasNaoLetivosRequest(
            dias=[DiaNaoLetivoItem(data=d, tipo="prova") for d in dias],
            frente_id=base["tech"],
            variante=variante,
            substituir=substituir,
        ),
    )


class TestCarregarNumCalendario:
    def test_grava_no_calendario_pedido(self, db, base):
        carregar(db, base, [PROVA_CC], COMPUTACAO)
        assert DiaNaoLetivoRepository(db).listar_variantes(
            base["semestre"], base["tech"]
        ) == sorted([COMPUTACAO, ENGENHARIAS])

    def test_substituir_nao_toca_no_calendario_vizinho(self, db, base):
        """O risco central da tela: os dois cursos moram na MESMA frente, e um
        `substituir` sem variante apagaria o calendário do outro."""
        carregar(db, base, [PROVA_CC], COMPUTACAO, substituir=True)
        do_banco = DiaNaoLetivoRepository(db).get_by_semestre(base["semestre"])
        assert sorted(d.data for d in do_banco) == sorted([PROVA_ENG, PROVA_CC])

    def test_a_mesma_data_cabe_nos_dois_calendarios(self, db, base):
        carregar(db, base, [PROVA_ENG], COMPUTACAO)
        do_banco = DiaNaoLetivoRepository(db).get_by_semestre(base["semestre"])
        assert [d.variante for d in do_banco] == [ENGENHARIAS, COMPUTACAO]

    def test_calendario_de_curso_sem_frente_e_recusado(self, db, base):
        """Seria um feriado nacional que só vale para alguns cursos — e, pior,
        ficaria invisível: a resolução só procura variante dentro da frente."""
        with pytest.raises(RegraDeNegocioError, match="precisa de uma frente"):
            CreateDiasNaoLetivosUseCase(db).execute(
                base["semestre"],
                CreateDiasNaoLetivosRequest(
                    dias=[DiaNaoLetivoItem(data=PROVA_CC, tipo="feriado")],
                    frente_id=None,
                    variante=COMPUTACAO,
                ),
            )

    def test_recarregar_o_mesmo_dia_e_ignorado(self, db, base):
        resultado = carregar(db, base, [PROVA_ENG], ENGENHARIAS)
        assert (resultado["criados"], resultado["ignorados"]) == (0, 1)


class TestRenomear:
    def pedido(self, base, nome):
        return RenomearCalendarioRequest(frente_id=base["tech"], nome=nome)

    def test_leva_junto_os_dias_o_padrao_da_frente_e_os_escopos(self, db, base):
        """O rótulo é a chave nas três tabelas. Deixar uma para trás desligaria
        o calendário dos escopos sem erro nenhum aparecer na tela.

        O escopo da fixture já nasce em `ENGENHARIAS` — é justamente o vínculo
        que tem de ser levado junto.
        """
        RenomearCalendarioUseCase(db).execute(
            base["semestre"], ENGENHARIAS, self.pedido(base, "Engenharias e Design")
        )

        repo = DiaNaoLetivoRepository(db)
        assert repo.listar_variantes(base["semestre"], base["tech"]) == [
            "Engenharias e Design"
        ]
        frente = db.query(FrenteModel).filter(FrenteModel.id == base["tech"]).first()
        assert frente.calendario_padrao == "Engenharias e Design"
        escopo = (
            db.query(ProjetoEscopoModel)
            .filter(ProjetoEscopoModel.id == base["escopo"])
            .first()
        )
        assert escopo.calendario == "Engenharias e Design"

    def test_nome_ja_usado_na_frente_e_recusado(self, db, base):
        carregar(db, base, [PROVA_CC], COMPUTACAO)
        with pytest.raises(RegraDeNegocioError, match="já tem um calendário"):
            RenomearCalendarioUseCase(db).execute(
                base["semestre"], ENGENHARIAS, self.pedido(base, COMPUTACAO)
            )

    def test_calendario_inexistente_e_recusado(self, db, base):
        with pytest.raises(RegraDeNegocioError, match="não tem um calendário"):
            RenomearCalendarioUseCase(db).execute(
                base["semestre"], "Medicina", self.pedido(base, "Outro")
            )


class TestApontarOEscopo:
    """⭐ A base de contagem é do ESCOPO, e escolhê-la é obrigatório.

    `projeto.calendario` era opcional e ninguém escolhia — os 22 projetos em
    produção estavam todos nulos, e a plataforma contava a união dos dias de
    todas as frentes.
    """

    def trocar(self, db, base, calendario):
        return UpdateEscopoProjetoUseCase(db).execute(
            base["escopo"], UpdateEscopoProjetoRequest(calendario=calendario)
        )

    def test_aceita_calendario_que_existe_na_frente_do_escopo(self, db, base):
        carregar(db, base, [PROVA_CC], COMPUTACAO)
        self.trocar(db, base, COMPUTACAO)

        escopo = (
            db.query(ProjetoEscopoModel)
            .filter(ProjetoEscopoModel.id == base["escopo"])
            .first()
        )
        assert escopo.calendario == COMPUTACAO

    def test_recusa_nome_que_nao_existe(self, db, base):
        """Um rótulo errado não daria erro na hora: simplesmente não casaria
        com dia algum, e o escopo contaria a semana de provas de ninguém."""
        with pytest.raises(RegraDeNegocioError, match="não tem um calendário chamado"):
            self.trocar(db, base, "Medicina")

    def test_nulo_e_recusado_quando_a_frente_tem_calendarios_nomeados(self, db, base):
        """⭐ O que faltava. Nulo numa frente com cursos é "não escolhi", e era
        exatamente esse estado que deixava a plataforma somando tudo."""
        with pytest.raises(RegraDeNegocioError, match="Escolha o calendário"):
            self.trocar(db, base, None)

    def test_a_mensagem_lista_as_opcoes(self, db, base):
        carregar(db, base, [PROVA_CC], COMPUTACAO)
        with pytest.raises(RegraDeNegocioError) as erro:
            self.trocar(db, base, None)

        assert ENGENHARIAS in str(erro.value) and COMPUTACAO in str(erro.value)

    def test_nao_mandar_o_campo_nao_mexe_no_calendario(self, db, base):
        """`exclude_unset`: editar só os dias vendidos não pode zerar a base."""
        UpdateEscopoProjetoUseCase(db).execute(
            base["escopo"], UpdateEscopoProjetoRequest(dias_uteis_vendidos=30)
        )

        escopo = (
            db.query(ProjetoEscopoModel)
            .filter(ProjetoEscopoModel.id == base["escopo"])
            .first()
        )
        assert escopo.calendario == ENGENHARIAS
