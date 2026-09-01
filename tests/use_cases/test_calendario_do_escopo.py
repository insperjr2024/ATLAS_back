"""O calendário que cada ESCOPO enxerga, contra o banco de verdade.

`tests/utils/test_calendario_variante.py` prova a regra de escolha com objetos
soltos. Aqui a mesma regra passa pelo model, pela unicidade e pela query — que
é onde ela de fato roda.

⭐ O caso central é `TestOCorteRealmenteCorta`. A versão anterior resolvia o
calendário por PROJETO e cortava só por variante, nunca por frente: todo
projeto enxergava a união dos dias de todas as frentes, e um escopo de Business
parava na semana de avaliação da Tech. É essa união que os testes daqui
proíbem de voltar.
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
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.frente_repository import FrenteRepository

SEMESTRE = 1
ENGENHARIAS = "Engenharias"
COMPUTACAO = "Ciência da Computação"

FERIADO = date(2026, 9, 7)
PROVA_ENG = date(2026, 9, 24)
PROVA_CC = date(2026, 10, 15)
PROVA_BUSINESS = date(2026, 9, 30)

TABELAS = [
    ProjetoModel.__table__,
    ProjetoEscopoModel.__table__,
    FrenteModel.__table__,
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
    """O retrato da base logo depois da migration.

    Business com um calendário só (variante nula, como sempre foi) e Tech com
    os dias que já estavam lá rotulados de "Engenharias", que é o que eles são.
    """
    business = FrenteModel(nome="Business", piso_banca=3)
    tech = FrenteModel(nome="Tech", piso_banca=2, calendario_padrao=ENGENHARIAS)
    db.add_all([business, tech])
    db.flush()

    db.add_all(
        [
            DiaNaoLetivoModel(
                semestre_id=SEMESTRE, frente_id=None, data=FERIADO, tipo="feriado"
            ),
            DiaNaoLetivoModel(
                semestre_id=SEMESTRE,
                frente_id=business.id,
                data=PROVA_BUSINESS,
                tipo="prova",
            ),
            DiaNaoLetivoModel(
                semestre_id=SEMESTRE,
                frente_id=tech.id,
                variante=ENGENHARIAS,
                data=PROVA_ENG,
                tipo="prova",
            ),
            DiaNaoLetivoModel(
                semestre_id=SEMESTRE,
                frente_id=tech.id,
                variante=COMPUTACAO,
                data=PROVA_CC,
                tipo="prova",
            ),
        ]
    )
    db.commit()
    return {"business": business.id, "tech": tech.id}


def escopo(db, frente_id, calendario=None):
    """Um escopo vendido, que é quem declara o calendário base (§5.4)."""
    p = ProjetoModel(
        nome="Projeto Alfa",
        cliente="Cliente",
        criado_por=1,
        status="em_andamento",
        dias_ambientacao=5,
    )
    db.add(p)
    db.flush()
    e = ProjetoEscopoModel(
        projeto_id=p.id,
        frente_id=frente_id,
        nome_customizado="Escopo",
        calendario=calendario,
        dias_uteis_vendidos=20,
    )
    db.add(e)
    db.commit()
    return e


def datas(registros):
    return sorted(d.data for d in registros)


class TestOCorteRealmenteCorta:
    """⚠ A regressão: o dia de OUTRA FRENTE não entra na conta."""

    def test_escopo_de_business_nao_ve_a_prova_da_tech(self, db, base):
        e = escopo(db, base["business"])
        vistos = datas(DiaNaoLetivoRepository(db).get_do_escopo(e))

        assert vistos == sorted([FERIADO, PROVA_BUSINESS])

    def test_escopo_da_tech_nao_ve_a_prova_de_business(self, db, base):
        e = escopo(db, base["tech"], calendario=ENGENHARIAS)
        vistos = datas(DiaNaoLetivoRepository(db).get_do_escopo(e))

        assert vistos == sorted([FERIADO, PROVA_ENG])

    def test_o_curso_vizinho_da_mesma_frente_tambem_fica_de_fora(self, db, base):
        e = escopo(db, base["tech"], calendario=ENGENHARIAS)

        assert PROVA_CC not in datas(DiaNaoLetivoRepository(db).get_do_escopo(e))

    def test_por_id_resolve_igual(self, db, base):
        e = escopo(db, base["business"])
        repo = DiaNaoLetivoRepository(db)

        assert datas(repo.get_do_escopo_id(e.id)) == datas(repo.get_do_escopo(e))

    def test_escopo_que_nao_existe_recebe_so_os_globais(self, db, base):
        """O calendário mais conservador possível, em vez de estourar."""
        assert datas(DiaNaoLetivoRepository(db).get_do_escopo_id(9999)) == [FERIADO]


class TestEscopoDeComputacao:
    def test_troca_a_semana_de_provas_das_engenharias_pela_dele(self, db, base):
        e = escopo(db, base["tech"], calendario=COMPUTACAO)
        vistos = datas(DiaNaoLetivoRepository(db).get_do_escopo(e))

        assert PROVA_CC in vistos
        assert PROVA_ENG not in vistos

    def test_continua_vendo_o_feriado_nacional(self, db, base):
        e = escopo(db, base["tech"], calendario=COMPUTACAO)

        assert FERIADO in datas(DiaNaoLetivoRepository(db).get_do_escopo(e))


class TestOrdemDasFrentes:
    """A regressão que o `calendario_padrao` causou na tela.

    O `get_all` herdado não ordenava, e o Postgres devolve na ordem física da
    tabela. O `UPDATE` que deu à Tech o calendário padrão reescreveu a linha
    dela e a jogou para o fim: no seletor de Calendários base a Tech saiu do
    segundo lugar e foi parar depois de Direito, sem que ninguém tivesse
    mudado nada de propósito.
    """

    def test_sai_por_id_e_nao_por_ordem_de_escrita(self, db, base):
        antes = [f.nome for f in FrenteRepository(db).get_all()]
        assert antes == ["Business", "Tech"]

        # Mexer na Tech é o que embaralhava a lista.
        db.query(FrenteModel).filter(FrenteModel.nome == "Tech").update(
            {FrenteModel.calendario_padrao: "Outro"}
        )
        db.commit()

        assert [f.nome for f in FrenteRepository(db).get_all()] == antes

    def test_get_ativas_segue_a_mesma_ordem(self, db, base):
        nomes = [f.nome for f in FrenteRepository(db).get_ativas()]
        assert nomes == ["Business", "Tech"]


class TestCargaPorCalendario:
    def test_a_mesma_data_cabe_em_dois_calendarios_da_mesma_frente(self, db, base):
        """O que a unicidade antiga proibia, e que motivou a mudança.

        `(semestre, frente, data)` fazia o PDF de um curso sobrescrever o do
        outro: duas provas no mesmo dia, uma por curso, não cabiam.
        """
        db.add(
            DiaNaoLetivoModel(
                semestre_id=SEMESTRE,
                frente_id=base["tech"],
                variante=COMPUTACAO,
                data=PROVA_ENG,
                tipo="prova",
            )
        )
        db.commit()

        eng = escopo(db, base["tech"], calendario=ENGENHARIAS)
        assert PROVA_ENG in datas(DiaNaoLetivoRepository(db).get_do_escopo(eng))

    def test_listar_variantes_nao_inventa_calendario_em_frente_sem_curso(self, db, base):
        repo = DiaNaoLetivoRepository(db)
        assert repo.listar_variantes(SEMESTRE, base["business"]) == []
        assert repo.listar_variantes(SEMESTRE, base["tech"]) == sorted(
            [COMPUTACAO, ENGENHARIAS]
        )

    def test_apagar_um_calendario_nao_toca_no_outro(self, db, base):
        """`substituir` ao recarregar o PDF de um curso — o risco de a tela
        apagar o calendário vizinho, que está na mesma frente."""
        repo = DiaNaoLetivoRepository(db)
        repo.delete_da_frente(SEMESTRE, base["tech"], COMPUTACAO)
        assert repo.listar_variantes(SEMESTRE, base["tech"]) == [ENGENHARIAS]

    def test_apagar_o_calendario_da_frente_nao_toca_no_global(self, db, base):
        repo = DiaNaoLetivoRepository(db)
        repo.delete_da_frente(SEMESTRE, base["tech"], ENGENHARIAS)
        e = escopo(db, base["tech"], calendario=ENGENHARIAS)
        assert FERIADO in datas(repo.get_do_escopo(e))
