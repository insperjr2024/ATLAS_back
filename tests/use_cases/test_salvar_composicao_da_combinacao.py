"""O que a tela de Configurações grava numa combinação — e o que ela recusa.

⭐ O teto de vagas passou a viajar junto com a matriz (2026-09-02): ele é da
COMBINAÇÃO, e não mais um número só para a plataforma inteira.

⚠ A recusa que importa aqui é **teto menor que o mínimo**. Uma banca assim é
impossível de fechar: a inscrição recusaria com "banca lotada" antes de
alguém completar o que a composição exige, e a banca ficaria atrasada para
sempre sem que ninguém entendesse por quê.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.configuracao.composicao_banca import (
    FrenteRegraRequest,
    SalvarComposicaoRequest,
    SalvarComposicaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

BUSINESS, TECH = 1, 3


class FakeRegraRepo:
    def __init__(self):
        self.gravou = None

    def definir(self, combinacao, linhas, vagas=None):
        self.gravou = {"combinacao": combinacao, "linhas": list(linhas), "vagas": vagas}


def montar():
    uc = SalvarComposicaoUseCase.__new__(SalvarComposicaoUseCase)
    uc.db = None
    uc.repository = FakeRegraRepo()
    uc.resolver = SimpleNamespace()
    return uc, uc.repository


def frente_regra(frente_id, min_membros=1, min_lideranca=1):
    return FrenteRegraRequest(
        frente_id=frente_id,
        min_membros=min_membros,
        max_membros=99,
        min_lideranca=min_lideranca,
        max_lideranca=99,
    )


def test_grava_o_teto_junto_com_a_matriz():
    uc, repo = montar()

    uc.execute(
        [BUSINESS, TECH],
        SalvarComposicaoRequest(
            frentes=[frente_regra(BUSINESS, 3), frente_regra(TECH, 2)], vagas=9
        ),
    )

    assert repo.gravou["combinacao"] == "1-3"
    assert repo.gravou["vagas"] == 9


def test_sem_teto_grava_nulo_e_a_combinacao_segue_o_global():
    uc, repo = montar()

    uc.execute([BUSINESS], SalvarComposicaoRequest(frentes=[frente_regra(BUSINESS, 3)]))

    assert repo.gravou["vagas"] is None


def test_recusa_teto_menor_que_o_minimo_da_combinacao():
    """Business 3 + 1 liderança = 4 pessoas; um teto de 3 nunca fecharia."""
    uc, repo = montar()

    with pytest.raises(RegraDeNegocioError) as erro:
        uc.execute(
            [BUSINESS],
            SalvarComposicaoRequest(frentes=[frente_regra(BUSINESS, 3)], vagas=3),
        )

    assert "menor que o mínimo" in str(erro.value)
    assert repo.gravou is None


def test_recusa_teto_zero():
    uc, _ = montar()

    with pytest.raises(RegraDeNegocioError):
        uc.execute(
            [BUSINESS],
            SalvarComposicaoRequest(frentes=[frente_regra(BUSINESS, 1, 0)], vagas=0),
        )


def test_recusa_combinacao_sem_todas_as_frentes():
    """Já valia antes do teto: salvar sem uma frente da combinação deixaria
    essa frente caindo no padrão em silêncio."""
    uc, _ = montar()

    with pytest.raises(RegraDeNegocioError):
        uc.execute([BUSINESS, TECH], SalvarComposicaoRequest(frentes=[frente_regra(BUSINESS)]))
