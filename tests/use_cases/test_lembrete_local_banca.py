"""§ 2026-09-10 — lembretes de local da banca, na contagem regressiva.

    ~24h antes, sem local ...... COORDENADORES do projeto
    ~12h e ~2h antes, sem local  TODOS do projeto
    ~1h antes (com/sem local) .. QUEM VAI ASSISTIR — o local, ou "NÃO INFORMADO"

Dublês à mão; `notificar` e os dois helpers de destinatário são trocados no
módulo via `monkeypatch`.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import src.use_cases.banca.lembrete_local as mod
from src.use_cases.banca.lembrete_local import LembreteLocalBancaUseCase

AGORA = datetime.now(timezone.utc).replace(tzinfo=None)

COORDS = {1}
TIME_PROJETO = {1, 2, 3}
ESCALADOS = [SimpleNamespace(usuario_id=10), SimpleNamespace(usuario_id=11)]


def _banca(*, daqui, local=None, realizado=False, cancelada=False, id=1):
    return SimpleNamespace(
        id=id,
        nome_projeto="ATLAS I",
        data_hora=(AGORA + daqui) if daqui is not None else None,
        realizado_em=AGORA if realizado else None,
        cancelada_em=AGORA if cancelada else None,
        local=local,
    )


@pytest.fixture
def rodar(monkeypatch):
    def _rodar(*bancas):
        enviados = []
        monkeypatch.setattr(mod, "coordenadores_do_projeto_da_banca", lambda db, b: set(COORDS))
        monkeypatch.setattr(mod, "pessoas_do_projeto_da_banca", lambda db, b: set(TIME_PROJETO))
        monkeypatch.setattr(
            mod, "notificar",
            lambda db, uid, msg, **kw: enviados.append((uid, msg, kw.get("chave"))),
        )

        class BancaRepoFake:
            def __init__(self, db): pass
            def get_all(self): return list(bancas)

        class CandRepoFake:
            def __init__(self, db): pass
            def get_by_banca(self, bid): return list(ESCALADOS)

        monkeypatch.setattr(mod, "BancaRepository", BancaRepoFake)
        monkeypatch.setattr(mod, "CandidaturaRepository", CandRepoFake)

        total = LembreteLocalBancaUseCase(db=None).execute()
        return total, enviados

    return _rodar


def _chaves(enviados):
    return {c for _, _, c in enviados}


def test_24h_sem_local_vai_pros_coordenadores(rodar):
    _, env = rodar(_banca(daqui=timedelta(hours=20)))
    assert {uid for uid, _, _ in env} == COORDS
    assert _chaves(env) == {"local_falta_24h:banca=1"}


def test_12h_sem_local_vai_pro_time_inteiro(rodar):
    _, env = rodar(_banca(daqui=timedelta(hours=8)))
    assert {uid for uid, _, _ in env} == TIME_PROJETO
    assert _chaves(env) == {"local_falta_12h:banca=1"}


def test_2h_sem_local_vai_pro_time_inteiro(rodar):
    _, env = rodar(_banca(daqui=timedelta(minutes=90)))
    assert {uid for uid, _, _ in env} == TIME_PROJETO
    assert _chaves(env) == {"local_falta_2h:banca=1"}


def test_com_local_nao_cobra_ninguem_do_projeto(rodar):
    _, env = rodar(_banca(daqui=timedelta(hours=8), local="Sala 401"))
    assert env == []


def test_1h_antes_com_local_avisa_quem_vai_assistir(rodar):
    _, env = rodar(_banca(daqui=timedelta(minutes=40), local="Sala 401, prédio 2"))
    assert {uid for uid, _, _ in env} == {10, 11}
    assert all("Sala 401, prédio 2" in msg for _, msg, _ in env)
    assert _chaves(env) == {"local_avaliadores:banca=1"}


def test_1h_antes_sem_local_avisa_nao_informado(rodar):
    _, env = rodar(_banca(daqui=timedelta(minutes=40)))
    # os avaliadores (10, 11) — o time do projeto não entra neste aviso
    assert {uid for uid, _, _ in env} == {10, 11}
    assert all("NÃO INFORMADO" in msg and "coordenadores" in msg for _, msg, _ in env)


def test_banca_realizada_cancelada_ou_sem_data_e_ignorada(rodar):
    total, env = rodar(
        _banca(daqui=timedelta(hours=8), realizado=True, id=1),
        _banca(daqui=timedelta(hours=8), cancelada=True, id=2),
        _banca(daqui=None, id=3),
        _banca(daqui=timedelta(hours=-1), id=4),
    )
    assert total == 0 and env == []


def test_fora_de_qualquer_janela_nao_dispara(rodar):
    _, env = rodar(_banca(daqui=timedelta(days=3)))
    assert env == []
