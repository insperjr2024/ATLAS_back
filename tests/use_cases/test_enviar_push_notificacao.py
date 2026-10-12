"""Push (2026-10-12): quem recebe, o que vai no payload e a limpeza de
inscrição morta. Banco em SQLite e `webpush` trocado por um dublê."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.models  # noqa: F401
import src.use_cases.notificacao.enviar_push_notificacao as mod
from src.database.database import Base
from src.models.push_inscricao_model import PushInscricaoModel
from src.models.usuario_model import UsuarioModel
from src.repositories.push_inscricao_repository import PushInscricaoRepository


@pytest.fixture
def fabrica(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[UsuarioModel.__table__, PushInscricaoModel.__table__])
    monkeypatch.setattr(
        mod,
        "get_settings",
        lambda: SimpleNamespace(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv", VAPID_SUBJECT="", SMTP_USER="x@y.org"),
    )
    return sessionmaker(bind=engine)


def _usuario(db, id, ativo=True, desativadas=None):
    db.add(
        UsuarioModel(
            id=id, nome=f"U{id}", email_insper=f"u{id}@x.com", senha_hash="x", posicao="consultor",
            ativo=ativo, notificacoes_email_desativadas=desativadas or [],
        )
    )
    db.commit()


def _aparelho(db, usuario_id, endpoint):
    PushInscricaoRepository(db).salvar(usuario_id=usuario_id, endpoint=endpoint, p256dh="k", auth="a", user_agent=None)


class Duble:
    def __init__(self, status_por_endpoint=None):
        self.chamadas = []
        self.status = status_por_endpoint or {}

    def __call__(self, **kwargs):
        self.chamadas.append(kwargs)
        status = self.status.get(kwargs["subscription_info"]["endpoint"])
        if status:
            erro = Exception("recusado")
            erro.response = SimpleNamespace(status_code=status)
            raise erro


def test_manda_pra_todos_os_aparelhos_com_payload_certo(fabrica):
    db = fabrica()
    _usuario(db, 1)
    _aparelho(db, 1, "https://push/a")
    _aparelho(db, 1, "https://push/b")
    envio = Duble()

    n = mod.enviar_push(
        usuario_id=1, tipo="banca_remarcada", titulo="Banca remarcada", corpo="Nova data", rota="/bancas?banca=3",
        webpush_fn=envio, session_factory=fabrica,
    )

    assert n == 2
    payload = json.loads(envio.chamadas[0]["data"])
    assert payload == {"titulo": "Banca remarcada", "corpo": "Nova data", "url": "/bancas?banca=3", "tipo": "banca_remarcada"}
    assert envio.chamadas[0]["vapid_claims"] == {"sub": "mailto:x@y.org"}
    assert all(i.ultimo_envio_em for i in PushInscricaoRepository(fabrica()).get_by_usuario(1))


def test_inscricao_morta_e_apagada_e_a_viva_continua(fabrica):
    db = fabrica()
    _usuario(db, 1)
    _aparelho(db, 1, "https://push/viva")
    _aparelho(db, 1, "https://push/morta")

    n = mod.enviar_push(
        usuario_id=1, tipo="x", titulo="t", corpo=None, rota=None,
        webpush_fn=Duble({"https://push/morta": 410}), session_factory=fabrica,
    )

    assert n == 1
    restantes = [i.endpoint for i in PushInscricaoRepository(fabrica()).get_by_usuario(1)]
    assert restantes == ["https://push/viva"]


def test_erro_temporario_nao_apaga(fabrica):
    db = fabrica()
    _usuario(db, 1)
    _aparelho(db, 1, "https://push/a")

    n = mod.enviar_push(
        usuario_id=1, tipo="x", titulo="t", corpo=None, rota=None,
        webpush_fn=Duble({"https://push/a": 503}), session_factory=fabrica,
    )

    assert n == 0
    assert len(PushInscricaoRepository(fabrica()).get_by_usuario(1)) == 1


def test_tipo_desligado_no_perfil_nao_vai(fabrica):
    db = fabrica()
    _usuario(db, 1, desativadas=["banca_aviso"])
    _aparelho(db, 1, "https://push/a")
    envio = Duble()

    n = mod.enviar_push(usuario_id=1, tipo="banca_aviso", titulo="t", corpo=None, rota=None, webpush_fn=envio, session_factory=fabrica)

    assert n == 0 and envio.chamadas == []


def test_desligamento_total_de_email_nao_desliga_push(fabrica):
    db = fabrica()
    _usuario(db, 1, desativadas=["__tudo__"])
    _aparelho(db, 1, "https://push/a")
    envio = Duble()

    n = mod.enviar_push(usuario_id=1, tipo="banca_remarcada", titulo="t", corpo=None, rota=None, webpush_fn=envio, session_factory=fabrica)

    assert n == 1


def test_inativo_nao_recebe(fabrica):
    db = fabrica()
    _usuario(db, 1, ativo=False)
    _aparelho(db, 1, "https://push/a")
    envio = Duble()

    assert mod.enviar_push(usuario_id=1, tipo="x", titulo="t", corpo=None, rota=None, webpush_fn=envio, session_factory=fabrica) == 0


def test_sem_chaves_nao_faz_nada(fabrica, monkeypatch):
    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY=""))
    envio = Duble()

    assert mod.enviar_push(usuario_id=1, tipo="x", titulo="t", corpo=None, rota=None, webpush_fn=envio, session_factory=fabrica) == 0
    assert envio.chamadas == []


def test_aparelho_troca_de_dono_em_vez_de_duplicar(fabrica):
    db = fabrica()
    _usuario(db, 1)
    _usuario(db, 2)
    _aparelho(db, 1, "https://push/a")
    _aparelho(db, 2, "https://push/a")

    repo = PushInscricaoRepository(fabrica())
    assert repo.get_by_usuario(1) == []
    assert [i.endpoint for i in repo.get_by_usuario(2)] == ["https://push/a"]


def test_cancelar_so_apaga_o_proprio_aparelho(fabrica):
    db = fabrica()
    _usuario(db, 1)
    _usuario(db, 2)
    _aparelho(db, 1, "https://push/a")

    assert PushInscricaoRepository(fabrica()).remover_por_endpoint("https://push/a", usuario_id=2) is False
    assert PushInscricaoRepository(fabrica()).remover_por_endpoint("https://push/a", usuario_id=1) is True
