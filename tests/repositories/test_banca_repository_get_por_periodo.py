"""2026-09-16, a pedido — o rodízio passa a rodar UMA VEZ por banca, não a
cada passada. `get_por_periodo` é o portão: uma banca com `push_executado_em`
preenchido nunca mais volta a aparecer pro push, esteja o piso coberto ou
não.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.banca_model import BancaModel
from src.repositories.banca_repository import BancaRepository

AGORA = datetime.now()


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[BancaModel.__table__])
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def _banca(db, *, dias, push_executado=False):
    b = BancaModel(
        nome_projeto="Alfa",
        coordenador_id=1,
        data_hora=AGORA + timedelta(days=dias),
        push_executado_em=AGORA if push_executado else None,
    )
    db.add(b)
    db.commit()
    return b


def test_banca_dentro_da_janela_sem_push_aparece(db):
    _banca(db, dias=3)

    resultado = BancaRepository(db).get_por_periodo(AGORA, AGORA + timedelta(days=7))

    assert len(resultado) == 1


def test_banca_com_push_ja_executado_nunca_mais_aparece(db):
    """O caso central do pedido: mesmo com a banca ainda dentro da janela de
    7 dias, se o push já rodou nela uma vez, não volta — nem que o piso
    tenha ficado descoberto de novo depois (isso não é responsabilidade
    desta query, é o efeito que ela garante)."""
    _banca(db, dias=3, push_executado=True)

    resultado = BancaRepository(db).get_por_periodo(AGORA, AGORA + timedelta(days=7))

    assert resultado == []


def test_banca_fora_da_janela_nao_aparece_mesmo_sem_push(db):
    _banca(db, dias=10)

    resultado = BancaRepository(db).get_por_periodo(AGORA, AGORA + timedelta(days=7))

    assert resultado == []
