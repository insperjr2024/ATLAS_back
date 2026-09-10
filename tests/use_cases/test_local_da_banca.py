"""§ 2026-09-10 — registrar o local da banca.

- só quem é do projeto avaliado (checado em `_exigir_do_projeto`)
- só até 1h antes da banca
- texto obrigatório
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import src.use_cases.banca.local_e_entrega as mod
from src.use_cases.banca.local_e_entrega import RegistrarLocalBancaUseCase
from src.utils.exceptions import RegraDeNegocioError

AGORA = datetime.now(timezone.utc).replace(tzinfo=None)


def _uc(monkeypatch, *, banca, do_projeto=True):
    monkeypatch.setattr(mod, "_banca_ou_erro", lambda db, bid: banca)

    def _exigir(db, b, uid):
        if not do_projeto:
            raise RegraDeNegocioError(
                "Só quem é do projeto avaliado por esta banca pode registrar isto."
            )

    monkeypatch.setattr(mod, "_exigir_do_projeto", _exigir)
    uc = RegistrarLocalBancaUseCase(db=None)
    uc.repository = SimpleNamespace(update=lambda bid, **kw: kw)
    return uc


def _banca(*, daqui, cancelada=False):
    return SimpleNamespace(
        id=1,
        data_hora=AGORA + daqui,
        cancelada_em=AGORA if cancelada else None,
    )


def test_registra_com_folga(monkeypatch):
    uc = _uc(monkeypatch, banca=_banca(daqui=timedelta(hours=3)))
    r = uc.execute(1, "  Sala 401, prédio 2  ", usuario_id=10)
    assert r["local"] == "Sala 401, prédio 2"


def test_menos_de_1h_trava(monkeypatch):
    uc = _uc(monkeypatch, banca=_banca(daqui=timedelta(minutes=40)))
    with pytest.raises(RegraDeNegocioError, match="menos de 1h"):
        uc.execute(1, "Sala 401", usuario_id=10)


def test_texto_vazio_recusado(monkeypatch):
    uc = _uc(monkeypatch, banca=_banca(daqui=timedelta(hours=3)))
    with pytest.raises(RegraDeNegocioError, match="onde a banca vai acontecer"):
        uc.execute(1, "   ", usuario_id=10)


def test_banca_cancelada_recusada(monkeypatch):
    uc = _uc(monkeypatch, banca=_banca(daqui=timedelta(hours=3), cancelada=True))
    with pytest.raises(RegraDeNegocioError, match="cancelada"):
        uc.execute(1, "Sala 401", usuario_id=10)


def test_quem_nao_e_do_projeto_recusado(monkeypatch):
    uc = _uc(monkeypatch, banca=_banca(daqui=timedelta(hours=3)), do_projeto=False)
    with pytest.raises(RegraDeNegocioError, match="do projeto avaliado"):
        uc.execute(1, "Sala 401", usuario_id=99)


def test_banca_sem_data_ainda_aceita(monkeypatch):
    banca = SimpleNamespace(id=1, data_hora=None, cancelada_em=None)
    uc = _uc(monkeypatch, banca=banca)
    r = uc.execute(1, "A definir — sala do 4º andar", usuario_id=10)
    assert "4º andar" in r["local"]
