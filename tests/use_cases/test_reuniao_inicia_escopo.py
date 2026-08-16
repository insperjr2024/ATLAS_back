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
from src.models.cronograma_etapa_model import CronogramaEtapaModel
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
    CronogramaEtapaModel.__table__,
]


@pytest.fixture
def db():
    """SQLite na memória com as seis tabelas que a regra toca.

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

    def test_sem_banca_marcada_a_largada_acontece_igual(self, db):
        """⭐ A trava INVERTEU de sentido.

        Antes a banca precisava estar marcada ANTES da reunião inicial, e o
        backend recusava com 422. A ordem do §6 é a oposta — reunião inicial →
        etapas → banca → entrega — porque é a reunião que abre a janela, e é
        dentro da janela que a banca precisa caber (§9).

        Agora quem cobra é o outro lado: marcar banca de escopo sem reunião
        inicial é que não passa (ver `test_banca_na_janela.py`).
        """
        projeto, escopo = montar(db, com_banca=False)

        resposta = registrar(db, projeto, QUA_05, escopo.id)

        assert resposta["escopo_iniciado"] is True
        db.refresh(escopo)
        assert escopo.data_inicio == QUA_05
        assert escopo.status == "em_andamento"

    def test_reuniao_geral_nao_inicia_nada(self, db):
        """Reunião sem escopo conta para o §7.2, mas não larga contagem."""
        projeto, escopo = montar(db)

        resposta = registrar(db, projeto, QUA_05, None)

        assert resposta["escopo_iniciado"] is False
        db.refresh(escopo)
        assert escopo.data_inicio is None

    def test_segunda_reuniao_para_o_mesmo_escopo_e_recusada(self, db):
        """Só existe UMA reunião por escopo — ela É a inicial. A segunda
        tentativa é recusada, não vira uma "segunda inicial" nem reinicia a
        contagem; corrigir a data é mover a que já existe."""
        projeto, escopo = montar(db)
        registrar(db, projeto, QUA_05, escopo.id)

        with pytest.raises(RegraDeNegocioError):
            registrar(db, projeto, SEG_10, escopo.id)

        db.refresh(escopo)
        assert escopo.data_inicio == QUA_05

    def test_segunda_reuniao_fora_de_ordem_tambem_e_recusada(self, db):
        """Mesmo numa data anterior à primeira, a segunda tentativa é
        recusada igual — não existe "a mais antiga vence"."""
        projeto, escopo = montar(db)
        registrar(db, projeto, QUI_06, escopo.id)

        with pytest.raises(RegraDeNegocioError):
            registrar(db, projeto, SEG_03, escopo.id)

        db.refresh(escopo)
        assert escopo.data_inicio == QUI_06

    def test_escopo_de_outro_projeto_e_recusado(self, db):
        projeto, _ = montar(db)
        _, escopo_alheio = montar(db)

        with pytest.raises(RegraDeNegocioError):
            registrar(db, projeto, QUA_05, escopo_alheio.id)


class TestMoverEApagar:
    def test_mover_a_reuniao_inicial_move_o_inicio(self, db):
        """"Registrei quarta, aconteceu quinta" tem que acertar a contagem —
        é o caso que fazia a data ficar velha quando ela era digitada à parte.

        Mover a largada zera o cronograma do escopo, então só a diretoria
        move direto (ver `UpdateReuniaoUseCase`); é como `eh_diretor=True`
        aqui."""
        projeto, escopo = montar(db)
        reuniao = registrar(db, projeto, QUA_05, escopo.id)

        UpdateReuniaoUseCase(db).execute(
            reuniao["id"],
            ReuniaoRequest(data_reuniao=QUI_06, projeto_escopo_id=escopo.id),
            eh_diretor=True,
        )

        db.refresh(escopo)
        assert escopo.data_inicio == QUI_06

    def test_mover_sem_mandar_o_escopo_preserva_o_vinculo(self, db):
        """PATCH só com o dia não pode desligar o escopo por omissão — seria
        perder a largada sem ninguém ter pedido."""
        projeto, escopo = montar(db)
        reuniao = registrar(db, projeto, QUA_05, escopo.id)

        resposta = UpdateReuniaoUseCase(db).execute(
            reuniao["id"], ReuniaoRequest(data_reuniao=QUI_06), eh_diretor=True
        )

        assert resposta["projeto_escopo_id"] == escopo.id
        db.refresh(escopo)
        assert escopo.data_inicio == QUI_06

    def test_mover_a_largada_sem_ser_diretor_e_recusado(self, db):
        """Quem não é diretor recebe o motivo e o convite a pedir, não um
        422 cru — mover a largada zera etapas, banca e entrega do escopo."""
        projeto, escopo = montar(db)
        reuniao = registrar(db, projeto, QUA_05, escopo.id)

        with pytest.raises(RegraDeNegocioError):
            UpdateReuniaoUseCase(db).execute(
                reuniao["id"],
                ReuniaoRequest(data_reuniao=QUI_06, projeto_escopo_id=escopo.id),
            )

        db.refresh(escopo)
        assert escopo.data_inicio == QUA_05

    def test_apagar_a_unica_reuniao_desfaz_o_inicio(self, db):
        projeto, escopo = montar(db)
        reuniao = registrar(db, projeto, QUA_05, escopo.id)

        DeleteReuniaoUseCase(db).execute(reuniao["id"])

        db.refresh(escopo)
        assert escopo.data_inicio is None
        assert escopo.status == "nao_iniciado"

    def test_apagar_e_registrar_de_novo_funciona(self, db):
        """Apagar a única reunião do escopo libera a vaga: como só existe UMA
        por escopo, é assim que se corrige "marquei errado", sem mexer em
        data (ver `TestMoverEApagar` para mover)."""
        projeto, escopo = montar(db)
        primeira = registrar(db, projeto, QUA_05, escopo.id)

        DeleteReuniaoUseCase(db).execute(primeira["id"])
        resposta = registrar(db, projeto, SEG_10, escopo.id)

        assert resposta["escopo_iniciado"] is True
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


class TestReuniaoGeralNoCronograma:
    """A aba Reuniões acabou: as duas reuniões são marcadas no calendário do
    cronograma, e por isso precisam caber no mesmo dia.

    Antes o UNIQUE era `(projeto, data)` e uma barrava a outra — o que na
    prática obrigava a escolher entre registrar a reunião geral da semana e dar
    a largada de um escopo novo no mesmo dia.
    """

    def test_a_reuniao_geral_aceita_observacoes(self, db):
        """O campo que substituiu a tela própria: sem ele, o que foi combinado
        na reunião não tem onde morar."""
        projeto, _ = montar(db)

        resposta = CreateReuniaoUseCase(db).execute(
            projeto.id,
            ReuniaoRequest(
                data_reuniao=QUA_05,
                observacoes="Cliente pediu para antecipar o diagnóstico",
            ),
            registrado_por=1,
        )

        assert resposta["tipo"] == "geral"
        assert resposta["observacoes"] == "Cliente pediu para antecipar o diagnóstico"

    def test_a_reuniao_inicial_tambem_aceita_observacoes(self, db):
        projeto, escopo = montar(db)

        resposta = CreateReuniaoUseCase(db).execute(
            projeto.id,
            ReuniaoRequest(
                data_reuniao=QUA_05,
                projeto_escopo_id=escopo.id,
                observacoes="Escopo alinhado com o cliente",
            ),
            registrado_por=1,
        )

        assert resposta["tipo"] == "inicial"
        assert resposta["observacoes"] == "Escopo alinhado com o cliente"

    def test_geral_e_inicial_cabem_no_mesmo_dia(self, db):
        projeto, escopo = montar(db)

        geral = CreateReuniaoUseCase(db).execute(
            projeto.id, ReuniaoRequest(data_reuniao=QUA_05), registrado_por=1
        )
        inicial = registrar(db, projeto, QUA_05, escopo.id)

        assert geral["tipo"] == "geral"
        assert inicial["tipo"] == "inicial"
        db.refresh(escopo)
        assert escopo.data_inicio == QUA_05

    def test_duas_gerais_no_mesmo_dia_nao(self, db):
        """O UNIQUE do MySQL não cobre NULL — quem barra é o use case."""
        projeto, _ = montar(db)
        CreateReuniaoUseCase(db).execute(
            projeto.id, ReuniaoRequest(data_reuniao=QUA_05), registrado_por=1
        )

        with pytest.raises(RegraDeNegocioError):
            CreateReuniaoUseCase(db).execute(
                projeto.id, ReuniaoRequest(data_reuniao=QUA_05), registrado_por=1
            )

    def test_editar_so_as_observacoes_preserva_o_vinculo(self, db):
        """`exclude_unset`: quem só corrige o texto não pode perder o escopo e
        derrubar a `data_inicio` junto."""
        projeto, escopo = montar(db)
        reuniao = registrar(db, projeto, QUA_05, escopo.id)

        atualizada = UpdateReuniaoUseCase(db).execute(
            reuniao["id"],
            ReuniaoRequest(data_reuniao=QUA_05, observacoes="Ata revisada"),
        )

        assert atualizada["observacoes"] == "Ata revisada"
        assert atualizada["projeto_escopo_id"] == escopo.id
        db.refresh(escopo)
        assert escopo.data_inicio == QUA_05
