"""Quem já enviou a grade do semestre, para a tela de Membros marcar quem falta.

Grade vazia não deixa linha no banco, então quem "enviou uma grade sem aula
nenhuma" não é distinguível de quem nunca enviou. O endpoint reflete isso: só
aparece quem tem ao menos uma faixa gravada.
"""

from datetime import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.grade_horaria_model import GradeHorariaModel
from src.models.semestre_model import SemestreModel
from src.use_cases.grade_horaria.grade_horaria import GradeHorariaUseCase

TABELAS = [SemestreModel.__table__, GradeHorariaModel.__table__]


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
def semestres(db):
    from datetime import date

    ativa = SemestreModel(nome="2026.2", inicio=date(2026, 7, 1), fim=date(2026, 12, 31), status="ativa")
    passada = SemestreModel(nome="2026.1", inicio=date(2026, 1, 1), fim=date(2026, 6, 30), status="arquivada")
    db.add_all([ativa, passada])
    db.commit()
    return {"ativa": ativa.id, "passada": passada.id}


def faixa(db, usuario_id, semestre_id, dia=0):
    db.add(
        GradeHorariaModel(
            usuario_id=usuario_id,
            semestre_id=semestre_id,
            dia_semana=dia,
            hora_inicio=time(7, 30),
            hora_fim=time(9, 30),
        )
    )
    db.commit()


class TestUsuarioIdsComGrade:
    def test_lista_so_quem_tem_faixa_no_semestre_ativo(self, db, semestres):
        faixa(db, 10, semestres["ativa"])
        faixa(db, 11, semestres["ativa"])
        faixa(db, 99, semestres["passada"])  # semestre errado, fica de fora

        resultado = GradeHorariaUseCase(db).usuario_ids_com_grade()
        assert resultado["usuario_ids"] == [10, 11]
        assert resultado["semestre_id"] == semestres["ativa"]

    def test_conta_uma_vez_quem_tem_varias_faixas(self, db, semestres):
        faixa(db, 10, semestres["ativa"], dia=0)
        faixa(db, 10, semestres["ativa"], dia=1)
        faixa(db, 10, semestres["ativa"], dia=2)

        assert GradeHorariaUseCase(db).usuario_ids_com_grade()["usuario_ids"] == [10]

    def test_ninguem_enviou(self, db, semestres):
        assert GradeHorariaUseCase(db).usuario_ids_com_grade()["usuario_ids"] == []

    def test_semestre_explicito(self, db, semestres):
        faixa(db, 7, semestres["passada"])
        assert GradeHorariaUseCase(db).usuario_ids_com_grade(semestres["passada"])["usuario_ids"] == [7]
