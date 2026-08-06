"""⭐ A regra crítica do §5.4, do lado de quem a dispara.

*"A contagem só recomeça quando o coordenador marca a reunião inicial do
próximo escopo **e a data da banca dele**"* — as duas metades viraram uma
coisa só: registrar a reunião semanal dizendo sobre qual escopo ela foi.

`projeto_escopo.data_inicio` deixou de ser digitada e passou a ser DERIVADA da
primeira reunião do escopo. Estes testes prendem as consequências disso, que
são o que se perde quando alguém volta a tratá-la como campo solto: mover a
reunião move o início, apagá-la desfaz o início, e escopo sem banca marcada
não larga.
"""

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.banca_escopo_model import BancaEscopoModel
from src.models.banca_model import BancaModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_model import ProjetoModel
from src.models.tarefa_model import ReuniaoSemanalModel
from src.use_cases.tarefa.tarefas import (
    CreateReuniaoUseCase,
    DeleteReuniaoUseCase,
    ReuniaoRequest,
    UpdateReuniaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

# Agosto de 2026: 3 é segunda, 5 quarta, 6 quinta, 10 a segunda seguinte.
SEG_03 = date(2026, 8, 3)
QUA_05 = date(2026, 8, 5)
QUI_06 = date(2026, 8, 6)
SEG_10 = date(2026, 8, 10)

TABELAS = [
    ProjetoModel.__table__,
    ProjetoEscopoModel.__table__,
    ReuniaoSemanalModel.__table__,
    BancaModel.__table__,
    BancaEscopoModel.__table__,
]


@pytest.fixture
def db():
    """SQLite na memória com as cinco tabelas que a regra toca.

    As FKs para `usuario` e `escopo` ficam apontando para tabelas ausentes de
    propósito: o SQLite não as cobra com o pragma desligado (o padrão), e criar
    o esquema inteiro só para exercitar uma regra de data seria ruído.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=TABELAS)
    sessao = sessionmaker(bind=engine)()
    try:
        yield sessao
    finally:
        sessao.close()


def montar(db, *, com_banca=True, dias=15):
    """Um projeto com um escopo vendido — com ou sem a data da banca marcada."""
    projeto = ProjetoModel(nome="Projeto Alfa", cliente="Cliente", criado_por=1)
    db.add(projeto)
    db.flush()

    escopo = ProjetoEscopoModel(
        projeto_id=projeto.id,
        nome_customizado="Elaboração Contratual",
        frente_id=1,
        dias_uteis_vendidos=dias,
        status="nao_iniciado",
    )
    db.add(escopo)
    db.flush()

    if com_banca:
        banca = BancaModel(
            nome_projeto=projeto.nome,
            coordenador_id=1,
            data_hora=datetime(2026, 8, 20, 14, 0),
        )
        db.add(banca)
        db.flush()
        db.add(BancaEscopoModel(banca_id=banca.id, projeto_escopo_id=escopo.id))

    db.commit()
    return projeto, escopo


def registrar(db, projeto, dia, escopo_id):
    return CreateReuniaoUseCase(db).execute(
        projeto.id,
        ReuniaoRequest(data_reuniao=dia, projeto_escopo_id=escopo_id),
        registrado_por=1,
    )


class TestLargadaDaContagem:
    def test_primeira_reuniao_do_escopo_inicia_a_contagem(self, db):
        projeto, escopo = montar(db)

        resposta = registrar(db, projeto, QUA_05, escopo.id)

        assert resposta["escopo_iniciado"] is True
        db.refresh(escopo)
        assert escopo.data_inicio == QUA_05
        assert escopo.status == "em_andamento"

    def test_sem_banca_marcada_a_largada_e_barrada(self, db):
        """§5.4 pede as DUAS: a reunião inicial e a data da banca."""
        projeto, escopo = montar(db, com_banca=False)

        with pytest.raises(RegraDeNegocioError):
            registrar(db, projeto, QUA_05, escopo.id)

        db.refresh(escopo)
        assert escopo.data_inicio is None
        assert escopo.status == "nao_iniciado"

    def test_reuniao_geral_nao_inicia_nada(self, db):
        """Reunião sem escopo conta para o §7.2, mas não larga contagem."""
        projeto, escopo = montar(db)

        resposta = registrar(db, projeto, QUA_05, None)

        assert resposta["escopo_iniciado"] is False
        db.refresh(escopo)
        assert escopo.data_inicio is None

    def test_segunda_reuniao_nao_reinicia_a_contagem(self, db):
        """A largada é a PRIMEIRA reunião — as seguintes não mexem na data."""
        projeto, escopo = montar(db)
        registrar(db, projeto, QUA_05, escopo.id)

        resposta = registrar(db, projeto, SEG_10, escopo.id)

        assert resposta["escopo_iniciado"] is False
        db.refresh(escopo)
        assert escopo.data_inicio == QUA_05

    def test_reuniao_anterior_puxa_o_inicio_para_tras(self, db):
        """Registrada fora de ordem, a mais antiga é que é a inicial."""
        projeto, escopo = montar(db)
        registrar(db, projeto, QUI_06, escopo.id)

        registrar(db, projeto, SEG_03, escopo.id)

        db.refresh(escopo)
        assert escopo.data_inicio == SEG_03

    def test_escopo_de_outro_projeto_e_recusado(self, db):
        projeto, _ = montar(db)
        _, escopo_alheio = montar(db)

        with pytest.raises(RegraDeNegocioError):
            registrar(db, projeto, QUA_05, escopo_alheio.id)


class TestMoverEApagar:
    def test_mover_a_reuniao_inicial_move_o_inicio(self, db):
        """"Registrei quarta, aconteceu quinta" tem que acertar a contagem —
        é o caso que fazia a data ficar velha quando ela era digitada à parte."""
        projeto, escopo = montar(db)
        reuniao = registrar(db, projeto, QUA_05, escopo.id)

        UpdateReuniaoUseCase(db).execute(
            reuniao["id"], ReuniaoRequest(data_reuniao=QUI_06, projeto_escopo_id=escopo.id)
        )

        db.refresh(escopo)
        assert escopo.data_inicio == QUI_06

    def test_mover_sem_mandar_o_escopo_preserva_o_vinculo(self, db):
        """PATCH só com o dia não pode desligar o escopo por omissão — seria
        perder a largada sem ninguém ter pedido."""
        projeto, escopo = montar(db)
        reuniao = registrar(db, projeto, QUA_05, escopo.id)

        resposta = UpdateReuniaoUseCase(db).execute(
            reuniao["id"], ReuniaoRequest(data_reuniao=QUI_06)
        )

        assert resposta["projeto_escopo_id"] == escopo.id
        db.refresh(escopo)
        assert escopo.data_inicio == QUI_06

    def test_apagar_a_unica_reuniao_desfaz_o_inicio(self, db):
        projeto, escopo = montar(db)
        reuniao = registrar(db, projeto, QUA_05, escopo.id)

        DeleteReuniaoUseCase(db).execute(reuniao["id"])

        db.refresh(escopo)
        assert escopo.data_inicio is None
        assert escopo.status == "nao_iniciado"

    def test_apagar_a_inicial_promove_a_seguinte(self, db):
        projeto, escopo = montar(db)
        primeira = registrar(db, projeto, QUA_05, escopo.id)
        registrar(db, projeto, SEG_10, escopo.id)

        DeleteReuniaoUseCase(db).execute(primeira["id"])

        db.refresh(escopo)
        assert escopo.data_inicio == SEG_10
        assert escopo.status == "em_andamento"

    def test_trocar_o_escopo_da_reuniao_acerta_os_dois_lados(self, db):
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
        banca = BancaModel(
            nome_projeto=projeto.nome, coordenador_id=1, data_hora=datetime(2026, 9, 11, 14, 0)
        )
        db.add(banca)
        db.flush()
        db.add(BancaEscopoModel(banca_id=banca.id, projeto_escopo_id=outro.id))
        db.commit()

        reuniao = registrar(db, projeto, QUA_05, escopo.id)
        UpdateReuniaoUseCase(db).execute(
            reuniao["id"], ReuniaoRequest(data_reuniao=QUA_05, projeto_escopo_id=outro.id)
        )

        db.refresh(escopo)
        db.refresh(outro)
        assert escopo.data_inicio is None, "o escopo que perdeu a reunião volta a não ter começado"
        assert outro.data_inicio == QUA_05

    def test_escopo_entregue_nao_tem_o_inicio_mexido(self, db):
        """🔒 A entrega congelou a janela (§5.4) — reabrir o início mudaria
        dias já fechados."""
        projeto, escopo = montar(db)
        reuniao = registrar(db, projeto, QUA_05, escopo.id)
        escopo.data_entrega_real = SEG_10
        escopo.status = "entregue"
        db.commit()

        DeleteReuniaoUseCase(db).execute(reuniao["id"])

        db.refresh(escopo)
        assert escopo.data_inicio == QUA_05
        assert escopo.status == "entregue"
