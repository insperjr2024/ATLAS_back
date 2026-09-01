"""Mover a largada PODA o cronograma — não zera mais.

A regra antiga apagava etapas, banca e entrega planejada ao primeiro dia de
diferença na reunião inicial. Era previsível e caríssima: mover a largada dois
dias custava o cronograma inteiro, que o coordenador redesenhava à mão
praticamente igual.

A régua nova é a **janela**: o que continua dentro dela continua; o que cruza
uma borda encolhe até a borda; só some o que não tem um único dia dentro.

Estes testes prendem as quatro decisões que a poda tomou, e que são
exatamente o que se perde quando alguém volta a zerar por precaução:

1. etapa dentro da janela nova sobrevive intacta;
2. etapa que cruza a borda é aparada, não apagada;
3. os dias de ajuste da diretoria são MANTIDOS — é a janela nova que se
   calcula com eles;
4. a banca só é desmarcada quando a data dela ficou fora.
"""

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.banca_escopo_model import BancaEscopoModel
from src.models.banca_model import BancaModel
from src.models.cronograma_etapa_model import CronogramaEtapaModel
from src.models.dia_nao_letivo_model import DiaNaoLetivoModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_model import ProjetoModel
from src.models.projeto_status_historico_model import ProjetoStatusHistoricoModel
from src.models.tarefa_model import ReuniaoSemanalModel
from src.repositories.cronograma_repository import CronogramaEtapaRepository
from src.use_cases.cronograma.podar_escopo import planejar_poda
from src.use_cases.tarefa.tarefas import (
    CreateReuniaoUseCase,
    ReuniaoRequest,
    UpdateReuniaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

# Agosto de 2026. Com 10 dias úteis vendidos e sem feriado:
#   largada 05/08 (quarta) → janela 05/08 a 18/08
#   largada 10/08 (segunda) → janela 10/08 a 21/08
QUA_05 = date(2026, 8, 5)
SEG_10 = date(2026, 8, 10)
FIM_DA_JANELA_ANTIGA = date(2026, 8, 18)
FIM_DA_JANELA_NOVA = date(2026, 8, 21)

TABELAS = [
    ProjetoModel.__table__,
    ProjetoEscopoModel.__table__,
    ReuniaoSemanalModel.__table__,
    BancaModel.__table__,
    BancaEscopoModel.__table__,
    CronogramaEtapaModel.__table__,
    DiaNaoLetivoModel.__table__,
    ProjetoStatusHistoricoModel.__table__,
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


def montar(db, *, dias=10, ajustados=0, banca_em=datetime(2026, 8, 20, 14, 0)):
    projeto = ProjetoModel(nome="Projeto Alfa", cliente="Cliente", criado_por=1)
    db.add(projeto)
    db.flush()

    escopo = ProjetoEscopoModel(
        projeto_id=projeto.id,
        nome_customizado="Elaboração Contratual",
        frente_id=1,
        dias_uteis_vendidos=dias,
        dias_uteis_ajustados=ajustados,
        status="nao_iniciado",
    )
    db.add(escopo)
    db.flush()

    if banca_em:
        banca = BancaModel(nome_projeto=projeto.nome, coordenador_id=1, data_hora=banca_em)
        db.add(banca)
        db.flush()
        db.add(BancaEscopoModel(banca_id=banca.id, projeto_escopo_id=escopo.id))

    db.commit()
    return projeto, escopo


def pintar(db, escopo, nome, inicio, fim):
    etapa = CronogramaEtapaModel(
        projeto_escopo_id=escopo.id,
        nome=nome,
        cor="#3B82F6",
        data_inicio=inicio,
        data_fim=fim,
        status="planejada",
        ordem=0,
        criado_por=1,
    )
    db.add(etapa)
    db.commit()
    return etapa


def largar(db, projeto, escopo, dia=QUA_05):
    return CreateReuniaoUseCase(db).execute(
        projeto.id,
        ReuniaoRequest(data_reuniao=dia, projeto_escopo_id=escopo.id),
        registrado_por=1,
    )


def mover(db, reuniao_id, escopo, dia, **kwargs):
    return UpdateReuniaoUseCase(db).execute(
        reuniao_id,
        ReuniaoRequest(data_reuniao=dia, projeto_escopo_id=escopo.id),
        eh_diretor_projetos=kwargs.get("eh_diretor_projetos", True),
    )


def etapas_de(db, escopo):
    return {e.nome: (e.data_inicio, e.data_fim) for e in CronogramaEtapaRepository(db).get_by_escopo(escopo.id)}


class TestOQueSobrevive:
    def test_etapa_inteira_dentro_da_janela_nova_nao_e_tocada(self, db):
        """O caso que motivou a mudança: mover a largada três dias para a
        frente não invalida o que continua dentro da janela."""
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo)
        pintar(db, escopo, "Diagnóstico", date(2026, 8, 13), date(2026, 8, 17))

        mover(db, reuniao["id"], escopo, SEG_10)

        assert etapas_de(db, escopo) == {
            "Diagnóstico": (date(2026, 8, 13), date(2026, 8, 17))
        }

    def test_etapa_que_cruza_o_inicio_e_aparada(self, db):
        """A largada andou para a frente e comeu o começo da etapa. O que
        sobra dela é o pedaço que continua dentro."""
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo)
        pintar(db, escopo, "Imersão", QUA_05, date(2026, 8, 12))

        resposta = mover(db, reuniao["id"], escopo, SEG_10)

        assert etapas_de(db, escopo) == {"Imersão": (SEG_10, date(2026, 8, 12))}
        assert resposta["cronograma_podado"]["etapas_aparadas"] == 1
        assert resposta["cronograma_podado"]["etapas_apagadas"] == 0

    def test_etapa_que_cruza_o_fim_e_aparada(self, db):
        """A largada andou para trás e a janela encurtou por cima."""
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo, dia=SEG_10)
        pintar(db, escopo, "Entrega parcial", date(2026, 8, 17), date(2026, 8, 21))

        mover(db, reuniao["id"], escopo, QUA_05)

        assert etapas_de(db, escopo) == {
            "Entrega parcial": (date(2026, 8, 17), FIM_DA_JANELA_ANTIGA)
        }

    def test_so_some_a_etapa_sem_nenhum_dia_dentro(self, db):
        """As três situações de uma vez — é assim que um cronograma real
        atravessa a mudança."""
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo)
        pintar(db, escopo, "Imersão", QUA_05, date(2026, 8, 12))
        pintar(db, escopo, "Diagnóstico", date(2026, 8, 13), date(2026, 8, 17))
        pintar(db, escopo, "Proposta", date(2026, 8, 20), date(2026, 8, 25))
        pintar(db, escopo, "Fora", date(2026, 8, 24), date(2026, 8, 28))

        resposta = mover(db, reuniao["id"], escopo, SEG_10)

        assert etapas_de(db, escopo) == {
            "Imersão": (SEG_10, date(2026, 8, 12)),
            "Diagnóstico": (date(2026, 8, 13), date(2026, 8, 17)),
            "Proposta": (date(2026, 8, 20), FIM_DA_JANELA_NOVA),
        }
        podado = resposta["cronograma_podado"]
        assert podado["etapas_apagadas"] == 1
        assert podado["etapas_aparadas"] == 2
        assert podado["janela_ate"] == FIM_DA_JANELA_NOVA.isoformat()

    def test_mover_sem_cronograma_pintado_nao_mexe_em_nada(self, db):
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo)

        resposta = mover(db, reuniao["id"], escopo, SEG_10)

        assert resposta["cronograma_podado"] == {
            "etapas_apagadas": 0,
            "etapas_aparadas": 0,
            "janela_ate": FIM_DA_JANELA_NOVA.isoformat(),
            "banca_desmarcada": None,
        }


class TestOsDiasDeAjuste:
    """Os dias que a diretoria autorizou são de TRABALHO, não da data.

    Zerá-los (o que a versão antiga fazia) encolheria a janela nova e mandaria
    para a poda etapas que a própria diretoria tinha liberado — e o prazo para
    pedir de novo, contado da largada, já teria vencido.
    """

    def test_os_dias_ajustados_sobrevivem_a_mudanca(self, db):
        projeto, escopo = montar(db, dias=10, ajustados=5)
        reuniao = largar(db, projeto, escopo)

        mover(db, reuniao["id"], escopo, SEG_10)

        db.refresh(escopo)
        assert escopo.dias_uteis_ajustados == 5

    def test_a_janela_nova_ja_conta_com_eles(self, db):
        """10 vendidos + 5 ajustados a partir de 10/08 vão até 28/08 — e é por
        isso que a etapa de 25/08 continua de pé."""
        projeto, escopo = montar(db, dias=10, ajustados=5)
        reuniao = largar(db, projeto, escopo)
        pintar(db, escopo, "Refino", date(2026, 8, 24), date(2026, 8, 25))

        resposta = mover(db, reuniao["id"], escopo, SEG_10)

        assert resposta["cronograma_podado"]["etapas_apagadas"] == 0
        assert etapas_de(db, escopo) == {"Refino": (date(2026, 8, 24), date(2026, 8, 25))}


class TestABanca:
    def test_banca_que_continua_na_janela_fica_marcada(self, db):
        """A banca de 20/08 cabe na janela nova (10/08 a 21/08) — desmarcá-la
        obrigaria o coordenador a remarcar a mesma data."""
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo)

        resposta = mover(db, reuniao["id"], escopo, SEG_10)

        assert resposta["cronograma_podado"]["banca_desmarcada"] is None
        banca = db.query(BancaModel).first()
        assert banca.data_hora == datetime(2026, 8, 20, 14, 0)

    def test_banca_que_ficou_fora_da_janela_e_desmarcada(self, db):
        """A largada voltou para 05/08 e a janela fecha em 18/08 — a banca de
        20/08 não cabe mais, e o §9 não deixa banca fora da janela."""
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo, dia=SEG_10)

        resposta = mover(db, reuniao["id"], escopo, QUA_05)

        assert resposta["cronograma_podado"]["banca_desmarcada"] == "2026-08-20T14:00:00"
        banca = db.query(BancaModel).first()
        assert banca.data_hora is None
        assert banca.id is not None, "a LINHA da banca não some — onze tabelas a referenciam"


class TestAsTravas:
    def test_banca_ja_realizada_barra_a_mudanca(self, db):
        """Depois da banca o que se pinta é correção, que nasce fora da janela
        — podar apagaria o retrabalho junto com o resultado da avaliação."""
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo)
        banca = db.query(BancaModel).first()
        banca.realizado_em = datetime(2026, 8, 20, 14, 0)
        db.commit()

        with pytest.raises(RegraDeNegocioError):
            mover(db, reuniao["id"], escopo, SEG_10)

    def test_escopo_entregue_barra_a_mudanca(self, db):
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo)
        escopo.data_entrega_real = date(2026, 8, 25)
        db.commit()

        with pytest.raises(RegraDeNegocioError):
            mover(db, reuniao["id"], escopo, SEG_10)

    def test_quem_nao_e_diretor_ve_o_tamanho_real_da_poda(self, db):
        """A recusa precisa dizer o que se perde de verdade. Dizer "zera o
        cronograma" quando a poda apaga uma etapa de quatro faz a pessoa
        desistir de um pedido que ela deveria fazer."""
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo)
        pintar(db, escopo, "Imersão", QUA_05, date(2026, 8, 12))
        pintar(db, escopo, "Fora", date(2026, 8, 24), date(2026, 8, 28))

        with pytest.raises(RegraDeNegocioError) as erro:
            mover(db, reuniao["id"], escopo, SEG_10, eh_diretor_projetos=False)

        mensagem = str(erro.value)
        assert "apagando 1 etapa" in mensagem
        assert "encurtando outra 1" in mensagem
        assert etapas_de(db, escopo).keys() == {"Imersão", "Fora"}, "a recusa não poda nada"

    def test_recusa_sem_perda_nao_inventa_estrago(self, db):
        projeto, escopo = montar(db)
        reuniao = largar(db, projeto, escopo)

        with pytest.raises(RegraDeNegocioError) as erro:
            mover(db, reuniao["id"], escopo, SEG_10, eh_diretor_projetos=False)

        assert "apagando" not in str(erro.value)


class TestSemLargadaNova:
    def test_escopo_que_perde_a_reuniao_perde_o_cronograma(self, db):
        """A reunião foi para outro escopo E mudou de dia: o escopo antigo
        fica sem largada, sem janela — e aí nada cabe. É o único caso em que
        a poda ainda apaga tudo."""
        projeto, escopo = montar(db)
        outro = ProjetoEscopoModel(
            projeto_id=projeto.id,
            nome_customizado="AI e Automações",
            frente_id=2,
            dias_uteis_vendidos=10,
            status="nao_iniciado",
        )
        db.add(outro)
        db.flush()
        db.commit()

        reuniao = largar(db, projeto, escopo)
        pintar(db, escopo, "Diagnóstico", date(2026, 8, 13), date(2026, 8, 17))

        resposta = UpdateReuniaoUseCase(db).execute(
            reuniao["id"],
            ReuniaoRequest(data_reuniao=SEG_10, projeto_escopo_id=outro.id),
            eh_diretor_projetos=True,
        )

        assert resposta["cronograma_podado"]["etapas_apagadas"] == 1
        assert etapas_de(db, escopo) == {}
        db.refresh(escopo)
        assert escopo.data_inicio is None


class TestPlanejarSemGravar:
    """A tela pergunta "o que eu perco se mudar para o dia 10?" antes de
    decidir. O plano não pode encostar no banco."""

    def test_planejar_nao_apaga_nada(self, db):
        projeto, escopo = montar(db)
        largar(db, projeto, escopo)
        pintar(db, escopo, "Fora", date(2026, 8, 24), date(2026, 8, 28))

        poda = planejar_poda(db, escopo.id, SEG_10)

        assert len(poda.apagar) == 1
        assert poda.mexe_em_alguma_coisa is True
        assert etapas_de(db, escopo).keys() == {"Fora"}
