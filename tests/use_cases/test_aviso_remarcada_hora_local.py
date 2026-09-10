"""§ 2026-09-10 — o aviso de banca remarcada saía em UTC.

`banca.data_hora` é UTC (convenção de `utils/fuso`). O corpo "De X para Y"
mostrava a hora crua — "De 23/09 às 21:45 para 14/10 às 21:45" para uma banca
que, no fuso local (BRT, UTC-3), é às 18:45.
"""

from datetime import date, datetime
from types import SimpleNamespace

from src.use_cases.notificacao import eventos
from src.use_cases.notificacao.eventos import _formatar_instante, notificar_banca_remarcada


def test_formatar_instante_converte_datetime_utc_para_local():
    # 23/09 21:45 UTC  ->  23/09 18:45 BRT
    assert _formatar_instante(datetime(2026, 9, 23, 21, 45)) == "23/09 às 18:45"


def test_formatar_instante_nao_mexe_em_date_puro_nem_none():
    assert _formatar_instante(date(2026, 9, 23)) == "23/09/2026"
    assert _formatar_instante(None) == "sem data"


def test_corpo_do_aviso_de_remarcada_usa_hora_local(monkeypatch):
    corpos = []
    monkeypatch.setattr(eventos, "todos_do_projeto", lambda db, pid: [1])
    monkeypatch.setattr(eventos, "inscritos_na_banca", lambda db, bid: [])
    monkeypatch.setattr(
        eventos, "registrar_varios",
        lambda db, dest, **kw: corpos.append(kw.get("corpo")),
    )

    notificar_banca_remarcada(
        db=None,
        projeto=SimpleNamespace(id=3, nome="ATLAS I"),
        banca_id=34,
        nome_escopo="Blend",
        de=datetime(2026, 9, 23, 21, 45),
        para=datetime(2026, 10, 14, 21, 45),
    )

    # Dois avisos (equipe do projeto + inscritos na banca); os dois em hora
    # local, nenhum com o "21:45" cru de UTC.
    assert corpos, "nenhum aviso disparado"
    for corpo in corpos:
        assert corpo.startswith("De 23/09 às 18:45 para 14/10 às 18:45.")
        assert "21:45" not in corpo
