"""§8, 2026-09-09 — a menos de 7 dias da banca, com a composição já completa,
ninguém sai sozinho.

Este arquivo prende o caso TOTAL (banca legada, sem `banca_frente`) de
`DeleteCandidaturaUseCase._saida_quebraria_composicao`: daqui a <= 7 dias E
`alocados >= piso` E `alocados - 1 < piso` — que pra número inteiro é
`alocados == piso`. A diretoria (`eh_gestao=True`) passa por cima. O caso POR
FRENTE (quem especificamente pode sair) está em
`test_desalocar_por_pessoa.py`.

Usa `piso_minimo_override` para não depender da matriz de composição.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.banca_frente_model import BancaFrenteModel
from src.models.banca_model import BancaModel
from src.models.candidatura_model import CandidaturaModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.candidatura.update_candidatura import DeleteCandidaturaUseCase
from src.utils.exceptions import RegraDeNegocioError

TABELAS = [
    UsuarioModel.__table__,
    BancaModel.__table__,
    CandidaturaModel.__table__,
    BancaFrenteModel.__table__,
]

# `data_hora` da banca é UTC sem tzinfo; o use case compara com agora_utc().
AGORA_UTC = datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=TABELAS)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def _banca(db, *, daqui_dias, piso, realizado=False):
    b = BancaModel(
        nome_projeto="Alfa",
        coordenador_id=1,
        data_hora=AGORA_UTC + timedelta(days=daqui_dias),
        piso_minimo_override=piso,
        realizado_em=AGORA_UTC if realizado else None,
    )
    db.add(b)
    db.flush()
    return b


def _candidatar(db, banca, quantos):
    ids = []
    for i in range(1, quantos + 1):
        c = CandidaturaModel(
            banca_id=banca.id, usuario_id=i, criado_em=AGORA_UTC, confirmado=False
        )
        db.add(c)
        db.flush()
        ids.append(c.id)
    db.commit()
    return ids


def test_perto_e_completa_barra_o_consultor(db):
    b = _banca(db, daqui_dias=3, piso=2)
    ids = _candidatar(db, b, 2)
    with pytest.raises(RegraDeNegocioError, match="menos de 7 dias"):
        DeleteCandidaturaUseCase(db).execute(ids[0])


def test_diretoria_passa_por_cima(db):
    b = _banca(db, daqui_dias=3, piso=2)
    ids = _candidatar(db, b, 2)
    assert DeleteCandidaturaUseCase(db).execute(ids[0], eh_gestao=True) is True


def test_composicao_incompleta_libera(db):
    b = _banca(db, daqui_dias=3, piso=3)
    ids = _candidatar(db, b, 2)  # 2 < 3, ainda falta gente
    assert DeleteCandidaturaUseCase(db).execute(ids[0]) is True


def test_longe_da_banca_libera(db):
    b = _banca(db, daqui_dias=20, piso=2)
    ids = _candidatar(db, b, 2)
    assert DeleteCandidaturaUseCase(db).execute(ids[0]) is True


def test_exatamente_no_limite_ainda_barra(db):
    b = _banca(db, daqui_dias=7, piso=1)
    ids = _candidatar(db, b, 1)
    with pytest.raises(RegraDeNegocioError, match="menos de 7 dias"):
        DeleteCandidaturaUseCase(db).execute(ids[0])


def test_banca_realizada_continua_barrando_com_a_mensagem_de_sempre(db):
    b = _banca(db, daqui_dias=-1, piso=2, realizado=True)
    ids = _candidatar(db, b, 2)
    with pytest.raises(RegraDeNegocioError, match="já foi realizada"):
        DeleteCandidaturaUseCase(db).execute(ids[0])
