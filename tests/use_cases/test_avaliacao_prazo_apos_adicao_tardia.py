"""2026-09-15 — quem foi ADICIONADO à banca depois da realização (diretoria
corrigindo a ficha, ver `update_candidatura.py`/`create_candidatura.py`)
conta o prazo de avaliação a partir de quando virou candidato, não da
realização da banca — senão nasceria já fora do prazo, sem nunca ter tido
chance de abrir o formulário.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.use_cases.avaliacao.create_avaliacao import (
    CreateAvaliacaoRequest,
    CreateAvaliacaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

AGORA = datetime.now()


class FakeCandidaturaRepo:
    def __init__(self, candidaturas):
        self._candidaturas = candidaturas

    def get_by_banca(self, banca_id):
        return self._candidaturas


class FakeAvaliacaoRepo:
    def get_by_banca(self, banca_id, sessao=None):
        return []

    def create(self, **kwargs):
        return SimpleNamespace(id=1, **kwargs)


def _uc(*, realizado_em, candidatura_criado_em):
    uc = CreateAvaliacaoUseCase.__new__(CreateAvaliacaoUseCase)
    uc.repository = FakeAvaliacaoRepo()
    uc.banca_repository = SimpleNamespace(
        get_by_id=lambda _id: SimpleNamespace(id=1, realizado_em=realizado_em, cancelada_em=None)
    )
    uc.sessao_repository = SimpleNamespace(get_corrente=lambda _id: SimpleNamespace(numero=1))
    uc.candidatura_repository = FakeCandidaturaRepo(
        [SimpleNamespace(usuario_id=7, criado_em=candidatura_criado_em)]
    )
    return uc


def _pedido():
    return CreateAvaliacaoRequest(banca_id=1, formulario_id=1)


def test_adicionado_muito_depois_da_realizacao_ainda_consegue_abrir():
    """Banca realizada há 20 dias (prazo normal já teria vencido), mas a
    candidatura foi criada HOJE — a diretoria acabou de adicionar a pessoa."""
    uc = _uc(realizado_em=AGORA - timedelta(days=20), candidatura_criado_em=AGORA)
    assert uc.execute(_pedido(), avaliador_id=7)["id"] == 1


def test_candidato_de_sempre_ainda_respeita_o_prazo_normal():
    """Quem já era candidato desde antes da realização segue a régua de
    sempre: 7 dias da REALIZAÇÃO, não da candidatura (bem mais antiga)."""
    uc = _uc(
        realizado_em=AGORA - timedelta(days=10),
        candidatura_criado_em=AGORA - timedelta(days=30),
    )
    with pytest.raises(RegraDeNegocioError, match="prazo de 7 dias"):
        uc.execute(_pedido(), avaliador_id=7)


def test_dentro_do_prazo_normal_continua_passando():
    uc = _uc(
        realizado_em=AGORA - timedelta(days=2),
        candidatura_criado_em=AGORA - timedelta(days=30),
    )
    assert uc.execute(_pedido(), avaliador_id=7)["id"] == 1
