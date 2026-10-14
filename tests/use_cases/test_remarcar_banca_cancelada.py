"""Marcar de novo uma banca CANCELADA (2026-10-13, corrigido).

Antes caía no caminho do adiamento: a data mudava, `cancelada_em` ficava, e
a banca remarcada seguia "cancelada" pra todo mundo. Agora é uma tentativa
nova: a cancelada fica arquivada em `banca_sessao` e a banca volta a ser
aberta. Reaproveita o mundo de dublês de `test_banca_na_janela.py`.
"""

from datetime import datetime
from types import SimpleNamespace

from tests.use_cases.test_banca_na_janela import ANA, DENTRO, marcar  # noqa: F401

CANCELADA_EM = datetime(2026, 9, 15, 18, 6)
DATA_CANCELADA = datetime(2026, 9, 18, 19, 30)


def banca_cancelada(data_hora=DATA_CANCELADA):
    return SimpleNamespace(
        id=50, data_hora=data_hora, realizado_em=None, resultado=None,
        cancelada_em=CANCELADA_EM, push_executado_em=datetime(2026, 9, 11), coordenador_id=ANA.id,
    )


def test_marcar_de_novo_reabre_a_banca_e_arquiva_a_cancelada(marcar):  # noqa: F811
    banca = banca_cancelada()
    executar, estado = marcar(banca_existente=banca)
    estado.sessoes.append(SimpleNamespace(id=1, banca_id=50, numero=1, data_hora=DATA_CANCELADA, realizado_em=None, resultado=None, encerrada_em=None))

    resposta = executar(DENTRO, quem=ANA)  # coordenador, sem justificativa, sem diretoria

    # "aberta" ou "atrasada" conforme o relógio de hoje; o que importa é não
    # ser mais "cancelada".
    assert resposta["status"] != "cancelada"
    assert banca.cancelada_em is None and banca.realizado_em is None and banca.resultado is None
    assert banca.push_executado_em is None, "o rodízio de alocação roda de novo na data nova"
    arquivada, nova = estado.sessoes
    assert arquivada.cancelada_em == CANCELADA_EM and arquivada.encerrada_em is not None
    assert arquivada.data_hora == DATA_CANCELADA
    assert nova.numero == 2 and nova.data_hora == DENTRO and nova.encerrada_em is None
    (remarcacao,) = estado.remarcacoes
    assert remarcacao["data_anterior"] == DATA_CANCELADA and remarcacao["data_nova"] == DENTRO
    assert "cancelada em 15/09/2026" in remarcacao["justificativa"]
    assert estado.notificou


def test_mesma_data_so_reabre(marcar):  # noqa: F811
    banca = banca_cancelada(data_hora=DENTRO)
    executar, estado = marcar(banca_existente=banca)
    estado.sessoes.append(SimpleNamespace(id=1, banca_id=50, numero=1, data_hora=DENTRO, realizado_em=None, resultado=None, encerrada_em=None))

    resposta = executar(DENTRO, quem=ANA)

    assert resposta["status"] != "cancelada" and banca.cancelada_em is None
    assert len(estado.sessoes) == 2 and estado.sessoes[0].cancelada_em == CANCELADA_EM
    assert estado.remarcacoes == [], "a data não mudou, não é remarcação"
