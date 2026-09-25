"""2026-09-24, a pedido — `get_by_banca` juntava notas de avaliação RASCUNHO
(formulário aberto e nunca enviado) com as de quem votou de verdade. Na
banca ÁRABE, um avaliador reabriu o formulário várias vezes sem nunca
enviar — cada reabertura virou uma linha de `avaliacao` nova em rascunho,
com nota 2 em "Plano de Ação" — e a média por critério caiu de ~4,0 (a
média real das 4 submissões) pra 2,6, puxada pelas notas de rascunho que
ninguém tinha confirmado enviar.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.avaliacao_model import AvaliacaoModel
from src.models.avaliacao_nota_model import AvaliacaoNotaModel
from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[AvaliacaoModel.__table__, AvaliacaoNotaModel.__table__])
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def _avaliacao(db, *, banca_id, status, nota_plano_de_acao):
    a = AvaliacaoModel(banca_id=banca_id, avaliador_id=1, formulario_id=1, status=status)
    db.add(a)
    db.commit()
    db.add(AvaliacaoNotaModel(avaliacao_id=a.id, pergunta_id=131, nota=nota_plano_de_acao))
    db.commit()
    return a


def test_so_traz_notas_de_avaliacao_submetida(db):
    for nota in (4, 5, 3, 4):
        _avaliacao(db, banca_id=46, status="submetida", nota_plano_de_acao=nota)
    for _ in range(10):
        _avaliacao(db, banca_id=46, status="rascunho", nota_plano_de_acao=2)

    notas = AvaliacaoNotaRepository(db).get_by_banca(46)

    assert len(notas) == 4
    assert sorted(float(n.nota) for n in notas) == [3.0, 4.0, 4.0, 5.0]


def test_nao_traz_nota_de_outra_banca(db):
    _avaliacao(db, banca_id=46, status="submetida", nota_plano_de_acao=4)
    _avaliacao(db, banca_id=99, status="submetida", nota_plano_de_acao=1)

    notas = AvaliacaoNotaRepository(db).get_by_banca(46)

    assert len(notas) == 1
    assert float(notas[0].nota) == 4.0
