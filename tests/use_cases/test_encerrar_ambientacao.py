"""🤖 A virada automática Ambientação → Em andamento (§4 + §5.3).

O que importa aqui não é a data (isso é `test_ambientacao.py`), é o EFEITO:
quem é virado, quem não é, e o que fica gravado no histórico. A linha sem
autor é parte da regra — é ela que faz a tela do Histórico escrever
"🤖 automático" em vez de acusar a última pessoa que mexeu no projeto.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.dia_nao_letivo_model import DiaNaoLetivoModel
from src.models.projeto_model import ProjetoModel
from src.models.projeto_status_historico_model import ProjetoStatusHistoricoModel
from src.use_cases.projeto.encerrar_ambientacao import EncerrarAmbientacaoUseCase

# Agosto de 2026: 3 é segunda, 7 sexta, 10 a segunda seguinte.
SEG_03 = date(2026, 8, 3)
QUA_05 = date(2026, 8, 5)
SEX_07 = date(2026, 8, 7)
SEG_10 = date(2026, 8, 10)

TABELAS = [
    ProjetoModel.__table__,
    ProjetoStatusHistoricoModel.__table__,
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


def projeto(db, *, status="ambientacao", kickoff=SEG_03, dias=5, nome="Projeto Alfa"):
    p = ProjetoModel(
        nome=nome,
        cliente="Cliente",
        criado_por=1,
        status=status,
        data_kickoff=kickoff,
        dias_ambientacao=dias,
    )
    db.add(p)
    db.commit()
    return p


def virar(db, referencia=SEG_10):
    return EncerrarAmbientacaoUseCase(db).execute(referencia=referencia)


class TestQuemVira:
    def test_ambientacao_vencida_vira_em_andamento(self, db):
        p = projeto(db)

        assert virar(db) == [p.id]

        db.refresh(p)
        assert p.status == "em_andamento"

    def test_ambientacao_em_curso_nao_vira(self, db):
        p = projeto(db)

        assert virar(db, referencia=QUA_05) == []

        db.refresh(p)
        assert p.status == "ambientacao"

    def test_o_ultimo_dia_ainda_nao_vira(self, db):
        """A borda: 03 + 5 dias úteis fecha na sexta 07, e sexta ainda é
        ambientação."""
        p = projeto(db)
        assert virar(db, referencia=SEX_07) == []
        db.refresh(p)
        assert p.status == "ambientacao"

    def test_feriado_adia_a_virada(self, db):
        """O calendário do Insper manda: com a quarta não letiva, a janela
        fecha na segunda e a virada só vem depois dela."""
        db.add(DiaNaoLetivoModel(semestre_id=1, frente_id=None, data=QUA_05, tipo="feriado"))
        db.commit()
        p = projeto(db)

        assert virar(db, referencia=SEG_10) == []

        db.refresh(p)
        assert p.status == "ambientacao"

    def test_dia_de_outra_frente_nao_adia(self, db):
        """A ambientação é do PROJETO: usar o calendário de uma frente faria o
        mesmo projeto sinérgico sair de Ambientação em datas diferentes
        conforme a frente que se olhasse."""
        db.add(DiaNaoLetivoModel(semestre_id=1, frente_id=7, data=QUA_05, tipo="prova"))
        db.commit()
        p = projeto(db)

        assert virar(db, referencia=SEG_10) == [p.id]

    def test_projeto_pausado_nao_e_tocado(self, db):
        """⏸ Pausar é parar o relógio — virar o status de quem está parado
        desfaria a decisão de quem pausou."""
        p = projeto(db, status="pausado")

        assert virar(db) == []

        db.refresh(p)
        assert p.status == "pausado"

    def test_outros_status_nao_sao_tocados(self, db):
        vendido = projeto(db, status="vendido", nome="Vendido")
        andando = projeto(db, status="em_andamento", nome="Andando")

        assert virar(db) == []

        db.refresh(vendido)
        db.refresh(andando)
        assert (vendido.status, andando.status) == ("vendido", "em_andamento")

    def test_sem_kickoff_nao_vira(self, db):
        """Não há de onde contar a janela — a saída continua manual."""
        p = projeto(db, kickoff=None)
        assert virar(db) == []
        db.refresh(p)
        assert p.status == "ambientacao"

    def test_sem_dias_de_ambientacao_nao_vira(self, db):
        p = projeto(db, dias=0)
        assert virar(db) == []
        db.refresh(p)
        assert p.status == "ambientacao"


class TestHistorico:
    def test_grava_a_transicao_sem_autor(self, db):
        p = projeto(db)

        virar(db)

        (linha,) = db.query(ProjetoStatusHistoricoModel).all()
        assert (linha.projeto_id, linha.status_anterior, linha.status_novo) == (
            p.id,
            "ambientacao",
            "em_andamento",
        )
        # 🤖 Sem autor: foi o calendário, não uma pessoa. É o que a tela lê
        # para escrever "automático".
        assert linha.alterado_por is None

    def test_rodar_de_novo_nao_duplica(self, db):
        """O job roda todo dia; o projeto já virado não gera segunda linha."""
        projeto(db)

        virar(db)
        assert virar(db) == []

        assert db.query(ProjetoStatusHistoricoModel).count() == 1


class TestUmProjetoSo:
    def test_executar_para_vira_apenas_o_alvo(self, db):
        alvo = projeto(db)
        outro = projeto(db, nome="Projeto Beta")

        assert EncerrarAmbientacaoUseCase(db).executar_para(alvo.id, referencia=SEG_10) is True

        db.refresh(outro)
        assert outro.status == "ambientacao"

    def test_executar_para_ignora_quem_nao_esta_em_ambientacao(self, db):
        p = projeto(db, status="em_andamento")
        assert EncerrarAmbientacaoUseCase(db).executar_para(p.id, referencia=SEG_10) is False
