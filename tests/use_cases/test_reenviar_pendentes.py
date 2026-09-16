"""`reenviar_emails_pendentes` — a orquestração da repescagem (2026-09-16,
incidente real). A consulta em si (o que conta como "pendente de verdade")
já é testada em `test_notificacao_repository_pendentes_de_email.py`; aqui o
que importa é que cada linha pendente vira uma chamada de reenfileiramento
com os dados certos, e a contagem devolvida bate.
"""

from datetime import datetime
from types import SimpleNamespace

from src.use_cases.notificacao.reenviar_pendentes import reenviar_emails_pendentes


def linha(id, usuario_id=1, tipo="banca_remarcada", titulo="Título", corpo=None, payload=None):
    return SimpleNamespace(id=id, usuario_id=usuario_id, tipo=tipo, titulo=titulo, corpo=corpo, payload=payload)


class NotificacaoRepositoryFake:
    def __init__(self, db):
        pass


def _montar(monkeypatch, pendentes):
    import src.use_cases.notificacao.reenviar_pendentes as mod

    estado = {"desde": None}

    class Repo(NotificacaoRepositoryFake):
        def get_pendentes_de_email(self, desde):
            estado["desde"] = desde
            return pendentes

    monkeypatch.setattr(mod, "NotificacaoRepository", Repo)
    chamadas = []

    def enfileirar_fake(**kwargs):
        chamadas.append(kwargs)

    return chamadas, enfileirar_fake, estado


def test_sem_pendentes_nao_chama_nada(monkeypatch):
    chamadas, enfileirar_fake, _ = _montar(monkeypatch, [])

    total = reenviar_emails_pendentes(db=None, enfileirar_fn=enfileirar_fake)

    assert total == 0
    assert chamadas == []


def test_cada_pendente_vira_uma_chamada_de_reenfileiramento(monkeypatch):
    pendentes = [
        linha(1, usuario_id=10, tipo="banca_remarcada", titulo="Banca remarcada", payload={"rota": "/bancas?banca=47"}),
        linha(2, usuario_id=20, tipo="tarefa_vencida", titulo="Tarefa vencida", corpo="texto"),
    ]
    chamadas, enfileirar_fake, _ = _montar(monkeypatch, pendentes)

    total = reenviar_emails_pendentes(db=None, enfileirar_fn=enfileirar_fake)

    assert total == 2
    assert chamadas[0] == {
        "notificacao_id": 1,
        "usuario_id": 10,
        "tipo": "banca_remarcada",
        "titulo": "Banca remarcada",
        "corpo": None,
        "rota": "/bancas?banca=47",
    }
    assert chamadas[1] == {
        "notificacao_id": 2,
        "usuario_id": 20,
        "tipo": "tarefa_vencida",
        "titulo": "Tarefa vencida",
        "corpo": "texto",
        "rota": None,
    }


def test_payload_none_nao_quebra_a_rota(monkeypatch):
    chamadas, enfileirar_fake, _ = _montar(monkeypatch, [linha(1, payload=None)])

    reenviar_emails_pendentes(db=None, enfileirar_fn=enfileirar_fake)

    assert chamadas[0]["rota"] is None


def test_janela_e_calculada_a_partir_de_agora(monkeypatch):
    from datetime import timedelta

    _, enfileirar_fake, estado = _montar(monkeypatch, [])
    agora = datetime(2026, 9, 16, 18, 0, 0)

    reenviar_emails_pendentes(
        db=None, agora=agora, janela=timedelta(hours=3), enfileirar_fn=enfileirar_fake
    )

    assert estado["desde"] == datetime(2026, 9, 16, 15, 0, 0)
