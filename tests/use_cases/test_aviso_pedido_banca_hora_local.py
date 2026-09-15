"""§ 2026-09-15 — os avisos de pedido de banca saíam em UTC.

`data_hora_pretendida` segue a convenção de `banca.data_hora` (utils/fuso): o
front manda `toISOString()`. Os avisos de fora da janela e de exceção de choque
formatavam a hora crua — "em 15/09/2026 às 17:00" para um pedido que, no fuso
local (BRT, UTC-3), é às 14:00. O mesmo erro do e-mail "Banca de FRUTAS I hoje
às 17:00", e o mesmo já corrigido em `remarcacao_solicitacao.py`.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca import excecao_choque, fora_janela

# 17:00 UTC = 14:00 em São Paulo.
PEDIDO = SimpleNamespace(
    data_hora_pretendida=datetime(2026, 9, 15, 17, 0),
    banca_id=7,
    solicitado_por=5,
    status="aprovada",
    resposta="ok",
)


@pytest.fixture
def mensagens(monkeypatch):
    enviadas = []
    for modulo in (fora_janela, excecao_choque):
        monkeypatch.setattr(
            modulo, "notificar", lambda db, uid, mensagem, **kw: enviadas.append(mensagem)
        )
    return enviadas


def _caso_de_uso(classe):
    caso = object.__new__(classe)
    caso.db = None
    caso.projeto_repository = SimpleNamespace(get_by_id=lambda pid: SimpleNamespace(nome="FRUTAS I"))
    caso.usuario_repository = SimpleNamespace(get_por_posicoes=lambda *p: [SimpleNamespace(id=1)])
    return caso


def _confere(mensagens):
    assert len(mensagens) == 1
    assert "15/09/2026 às 14:00" in mensagens[0]
    assert "17:00" not in mensagens[0]


def test_fora_janela_aviso_a_diretoria(mensagens):
    _caso_de_uso(fora_janela.SolicitarForaJanelaUseCase)._avisar_diretoria(
        PEDIDO, SimpleNamespace(projeto_id=3)
    )
    _confere(mensagens)


def test_fora_janela_aviso_a_quem_pediu(mensagens):
    _caso_de_uso(fora_janela.DecidirForaJanelaUseCase)._avisar_quem_pediu(PEDIDO)
    _confere(mensagens)


def test_excecao_choque_aviso_a_diretoria(mensagens):
    _caso_de_uso(excecao_choque.SolicitarExcecaoChoqueUseCase)._avisar_diretoria(
        PEDIDO, SimpleNamespace(nome_projeto="Beta"), SimpleNamespace(projeto_id=3)
    )
    _confere(mensagens)


def test_excecao_choque_aviso_a_quem_pediu(mensagens):
    _caso_de_uso(excecao_choque.DecidirExcecaoChoqueUseCase)._avisar_quem_pediu(PEDIDO)
    _confere(mensagens)
