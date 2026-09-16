"""2026-09-15 — apagar uma candidatura cancela a troca pendente dela.

`solicitacao_troca.candidatura_id` é SET NULL, não CASCADE: apagar a
candidatura por fora do fluxo de troca (ex.: diretoria removendo alguém
direto da banca) zerava a referência sozinho, mas o pedido continuava
"pendente" pra sempre — órfão, comparando uma composição contra ela mesma
(a pessoa já nem é mais candidata) e concluindo "qualquer um serve", mesmo
quando a vaga original era de uma frente específica. Caso real: a banca do
ÁRABE tinha um pedido aberto de alguém já removido, e virou "54 pessoas
podem confirmar" — o pool geral inteiro, sem nenhuma restrição.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.avaliacao_model import AvaliacaoModel
from src.models.banca_frente_model import BancaFrenteModel
from src.models.banca_model import BancaModel
from src.models.candidatura_model import CandidaturaModel
from src.models.solicitacao_troca_model import SolicitacaoTrocaModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.candidatura.update_candidatura import DeleteCandidaturaUseCase

TABELAS = [
    UsuarioModel.__table__,
    BancaModel.__table__,
    CandidaturaModel.__table__,
    BancaFrenteModel.__table__,
    SolicitacaoTrocaModel.__table__,
    AvaliacaoModel.__table__,
]

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


def _banca(db, *, daqui_dias=20, piso=1):
    b = BancaModel(
        nome_projeto="Alfa",
        coordenador_id=1,
        data_hora=AGORA_UTC + timedelta(days=daqui_dias),
        piso_minimo_override=piso,
    )
    db.add(b)
    db.flush()
    return b


def _candidatura(db, banca, usuario_id):
    c = CandidaturaModel(banca_id=banca.id, usuario_id=usuario_id, criado_em=AGORA_UTC, confirmado=False)
    db.add(c)
    db.commit()
    return c


def _solicitacao_aberta(db, banca, candidatura, usuario_original_id):
    s = SolicitacaoTrocaModel(
        banca_id=banca.id,
        usuario_original_id=usuario_original_id,
        candidatura_id=candidatura.id,
        criado_em=AGORA_UTC,
        status="pendente",
    )
    db.add(s)
    db.commit()
    return s


def test_apagar_candidatura_cancela_a_troca_pendente_dela(db):
    banca = _banca(db)
    candidatura = _candidatura(db, banca, usuario_id=7)
    solicitacao = _solicitacao_aberta(db, banca, candidatura, usuario_original_id=7)

    assert DeleteCandidaturaUseCase(db).execute(candidatura.id, eh_gestao=True) is True

    # ⚠ Não confere `candidatura_id is None` aqui: é a FK SET NULL do
    # Postgres fazendo isso, e o SQLite deste teste não aplica ação de FK
    # sem `PRAGMA foreign_keys=ON` — o que importa pro use case é o STATUS.
    db.refresh(solicitacao)
    assert solicitacao.status == "cancelada"


def test_nao_mexe_em_troca_ja_confirmada_ou_cancelada(db):
    """Só a PENDENTE é afetada — uma já resolvida é histórico, não deve
    virar 'cancelada' por cima de um status que já contava outra história."""
    banca = _banca(db)
    candidatura = _candidatura(db, banca, usuario_id=7)
    solicitacao = _solicitacao_aberta(db, banca, candidatura, usuario_original_id=7)
    solicitacao.status = "confirmada"
    db.commit()

    DeleteCandidaturaUseCase(db).execute(candidatura.id, eh_gestao=True)

    db.refresh(solicitacao)
    assert solicitacao.status == "confirmada"


def test_candidatura_sem_troca_nenhuma_continua_saindo_normal(db):
    banca = _banca(db)
    candidatura = _candidatura(db, banca, usuario_id=7)

    assert DeleteCandidaturaUseCase(db).execute(candidatura.id, eh_gestao=True) is True
