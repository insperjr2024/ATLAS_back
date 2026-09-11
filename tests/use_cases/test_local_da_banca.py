"""§ 2026-09-10 — registrar o local da banca.

- quem é do projeto avaliado OU a diretoria de projetos (`_exigir_pode_mexer`)
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

CONSULTOR = SimpleNamespace(id=10, posicao="consultor")
DIRETORIA = SimpleNamespace(id=99, posicao="diretor_projetos")
DE_FORA = SimpleNamespace(id=77, posicao="consultor")


def _uc(monkeypatch, *, banca, do_projeto=True):
    monkeypatch.setattr(mod, "_banca_ou_erro", lambda db, bid: banca)

    def _exigir(db, b, current_user):
        # espelha o real: diretoria passa; senão, tem de ser do projeto
        if getattr(current_user, "posicao", None) == "diretor_projetos":
            return
        if not do_projeto:
            raise RegraDeNegocioError(
                "Só quem é do projeto avaliado por esta banca (ou a diretoria "
                "de projetos) pode registrar isto."
            )

    monkeypatch.setattr(mod, "_exigir_pode_mexer", _exigir)
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
    r = uc.execute(1, "  Sala 401, prédio 2  ", CONSULTOR)
    assert r["local"] == "Sala 401, prédio 2"


def test_menos_de_1h_trava(monkeypatch):
    uc = _uc(monkeypatch, banca=_banca(daqui=timedelta(minutes=40)))
    with pytest.raises(RegraDeNegocioError, match="menos de 1h"):
        uc.execute(1, "Sala 401", CONSULTOR)


def test_texto_vazio_recusado(monkeypatch):
    uc = _uc(monkeypatch, banca=_banca(daqui=timedelta(hours=3)))
    with pytest.raises(RegraDeNegocioError, match="onde a banca vai acontecer"):
        uc.execute(1, "   ", CONSULTOR)


def test_banca_cancelada_recusada(monkeypatch):
    uc = _uc(monkeypatch, banca=_banca(daqui=timedelta(hours=3), cancelada=True))
    with pytest.raises(RegraDeNegocioError, match="cancelada"):
        uc.execute(1, "Sala 401", CONSULTOR)


def test_quem_nao_e_do_projeto_recusado(monkeypatch):
    uc = _uc(monkeypatch, banca=_banca(daqui=timedelta(hours=3)), do_projeto=False)
    with pytest.raises(RegraDeNegocioError, match="do projeto avaliado"):
        uc.execute(1, "Sala 401", DE_FORA)


def test_diretoria_de_projetos_registra_mesmo_sem_ser_do_projeto(monkeypatch):
    uc = _uc(monkeypatch, banca=_banca(daqui=timedelta(hours=3)), do_projeto=False)
    r = uc.execute(1, "Auditório central", DIRETORIA)
    assert r["local"] == "Auditório central"


def test_banca_sem_data_ainda_aceita(monkeypatch):
    banca = SimpleNamespace(id=1, data_hora=None, cancelada_em=None)
    uc = _uc(monkeypatch, banca=banca)
    r = uc.execute(1, "A definir — sala do 4º andar", CONSULTOR)
    assert "4º andar" in r["local"]
