"""`get_pendentes_de_email` — a consulta por trás da repescagem de e-mail
perdido (2026-09-16, incidente real, ver `reenviar_pendentes.py`).

`email_enviado_em` nulo tem três leituras possíveis: nunca foi tentado (o
caso que este método existe para achar), tentou e falhou (idem), ou nasceu
assim de propósito e vai continuar nulo pra sempre (broadcast de troca com
`enviar_email=False`, e marcação de leitura de condição). Os testes aqui
protegem a fronteira entre o primeiro grupo e o terceiro.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.notificacao_model import NotificacaoModel
from src.repositories.notificacao_repository import NotificacaoRepository

AGORA = datetime(2026, 9, 16, 18, 0, 0)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[NotificacaoModel.__table__])
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()


def _linha(db, **kwargs):
    padrao = dict(
        usuario_id=1,
        tipo="banca_remarcada",
        origem="evento",
        titulo="titulo",
        chave_dedup=f"k{id(kwargs)}",
        criado_em=AGORA,
        email_enviado_em=None,
    )
    padrao.update(kwargs)
    linha = NotificacaoModel(**padrao)
    db.add(linha)
    db.commit()
    return linha


def test_evento_pendente_e_recente_aparece(db):
    _linha(db, chave_dedup="k1")

    resultado = NotificacaoRepository(db).get_pendentes_de_email(desde=AGORA - timedelta(hours=1))

    assert len(resultado) == 1


def test_evento_ja_enviado_nao_aparece(db):
    _linha(db, chave_dedup="k1", email_enviado_em=AGORA)

    resultado = NotificacaoRepository(db).get_pendentes_de_email(desde=AGORA - timedelta(hours=1))

    assert resultado == []


def test_evento_antigo_fora_da_janela_nao_aparece(db):
    _linha(db, chave_dedup="k1", criado_em=AGORA - timedelta(hours=5))

    resultado = NotificacaoRepository(db).get_pendentes_de_email(desde=AGORA - timedelta(hours=1))

    assert resultado == []


def test_troca_banca_fica_de_fora_mesmo_pendente_e_recente(db):
    """O broadcast de `_notificar_elegiveis` passa `enviar_email=False` de
    propósito — sem coluna própria pra guardar essa intenção, excluir o tipo
    inteiro é a única forma segura de não reenviar spam a cada passada."""
    _linha(db, chave_dedup="k1", tipo="troca_banca")

    resultado = NotificacaoRepository(db).get_pendentes_de_email(desde=AGORA - timedelta(hours=1))

    assert resultado == []


def test_condicao_de_dispensa_fica_de_fora(db):
    """`kickoff_pendente` como `origem=condicao` só nasce quando a pessoa
    dispensa (`marcar_condicao_lida`) — nunca tenta e-mail, nulo pra sempre
    por design, não é uma falha a repescar."""
    _linha(db, chave_dedup="k1", tipo="kickoff_pendente", origem="condicao")

    resultado = NotificacaoRepository(db).get_pendentes_de_email(desde=AGORA - timedelta(hours=1))

    assert resultado == []


@pytest.mark.parametrize("tipo", ["tarefa_vencida", "banca_hoje"])
def test_condicao_com_email_de_verdade_e_reenviada(db, tipo):
    """Exceção da exceção: `tarefa_vencida`/`banca_hoje` SÃO `origem=condicao`
    mas `rodar_lembrete_condicoes` os cria com `enfileirar` junto — precisam
    continuar elegíveis à repescagem."""
    _linha(db, chave_dedup="k1", tipo=tipo, origem="condicao")

    resultado = NotificacaoRepository(db).get_pendentes_de_email(desde=AGORA - timedelta(hours=1))

    assert len(resultado) == 1
