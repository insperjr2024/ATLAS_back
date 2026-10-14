"""Pendências dos formulários fechados, por pessoa (2026-10-13)."""

from datetime import datetime
from types import SimpleNamespace

from src.use_cases.desempenho_lote.pendencias_fechados import ListarPendenciasFechadosUseCase


def lote(id, nome, fim, override=None, tipo="periodico"):
    return SimpleNamespace(id=id, nome=nome, tipo=tipo, override_manual=override, data_inicio=datetime(2026, 9, 1), data_fim=fim)


def pendencia(avaliador_id, nome, avaliado, respondida=False, projeto="ALFA"):
    return {"avaliador_id": avaliador_id, "avaliador_nome": nome, "avaliado_id": 99, "avaliado_nome": avaliado, "form_type": "consultor", "projeto_ids": [1], "projeto_nomes": [projeto], "projeto_escopo_id": None, "escopo_nome": None, "respondida": respondida}


def _uc(lotes, pendencias_por_lote, agora=datetime(2026, 10, 13)):
    uc = ListarPendenciasFechadosUseCase.__new__(ListarPendenciasFechadosUseCase)
    uc.lote_repo = SimpleNamespace(get_all=lambda: lotes)
    uc.pendencias = SimpleNamespace(execute=lambda lote_id: pendencias_por_lote.get(lote_id))
    return uc


def test_agrupa_por_pessoa_e_diz_o_lote():
    lotes = [
        lote(1, "Periódica setembro", datetime(2026, 9, 30)),
        lote(2, "Finalização BLEND I", datetime(2026, 10, 5), tipo="finalizacao"),
        lote(3, "Periódica outubro", datetime(2026, 11, 30)),  # ainda aberto
    ]
    pend = {
        1: [pendencia(10, "Ana", "Bia"), pendencia(10, "Ana", "Caio"), pendencia(11, "Duda", "Bia", respondida=True)],
        2: [pendencia(10, "Ana", "Eva"), pendencia(12, "Fabio", "Eva")],
        3: [pendencia(13, "Gui", "Eva")],
    }

    resultado = _uc(lotes, pend).execute()

    assert [r["avaliador_nome"] for r in resultado] == ["Ana", "Fabio"]
    ana = resultado[0]
    assert ana["total"] == 3
    # Fechado mais recente primeiro.
    assert [x["lote_nome"] for x in ana["lotes"]] == ["Finalização BLEND I", "Periódica setembro"]
    assert ana["lotes"][1]["pendentes"] == 2
    assert ana["lotes"][1]["itens"][0]["avaliado_nome"] == "Bia"
    assert "Duda" not in [r["avaliador_nome"] for r in resultado], "quem respondeu tudo não aparece"
    assert "Gui" not in [r["avaliador_nome"] for r in resultado], "lote aberto fica de fora"


def test_override_manda_mais_que_a_data():
    lotes = [
        lote(1, "Fechado na mão", datetime(2026, 12, 1), override="fechado"),
        lote(2, "Reaberto na mão", datetime(2026, 9, 1), override="aberto"),
    ]
    pend = {1: [pendencia(10, "Ana", "Bia")], 2: [pendencia(11, "Duda", "Bia")]}

    resultado = _uc(lotes, pend).execute()

    assert [r["avaliador_nome"] for r in resultado] == ["Ana"]


def test_sem_fechados_devolve_vazio():
    assert _uc([lote(1, "Aberto", datetime(2026, 12, 1))], {1: [pendencia(10, "Ana", "Bia")]}).execute() == []
