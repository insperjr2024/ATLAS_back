"""O mapa da carteira (`get_carteira._saude`): cor vigente por pilar, status
geral e tendência contra o ciclo anterior, a partir do histórico de um
projeto (da linha mais nova pra mais antiga)."""

from datetime import datetime
from types import SimpleNamespace

from src.use_cases.health_track.get_carteira import _saude
from src.utils.health_track_status import ReguasStatus

PILARES = [1, 2, 3]
REGRA = SimpleNamespace(
    vigente_desde=datetime(2026, 1, 1),
    verde_max_amarelos=1,
    verde_max_vermelhos=0,
    vermelho_min_amarelos=3,
    vermelho_min_vermelhos=1,
)
REGUAS = ReguasStatus([REGRA])


def ciclo(em: datetime, cores: dict) -> list:
    return [SimpleNamespace(pilar_id=pid, cor=cor, avaliado_em=em) for pid, cor in cores.items()]


def test_sem_historico():
    r = _saude([], PILARES, REGUAS)
    assert r["status_geral"] is None
    assert r["pilares"] == {"1": None, "2": None, "3": None}
    assert r["total_ciclos"] == 0
    assert r["algum_vermelho"] is False


def test_um_ciclo_completo_da_status_sem_tendencia():
    hist = ciclo(datetime(2026, 10, 1), {1: "verde", 2: "amarelo", 3: "verde"})
    r = _saude(hist, PILARES, REGUAS)
    assert r["status_geral"]["pela_regra_atual"] == "verde"
    assert r["status_anterior"] is None
    assert r["pilares"]["2"]["cor"] == "amarelo"
    assert r["total_ciclos"] == 1


def test_dois_ciclos_dao_a_tendencia():
    hist = ciclo(datetime(2026, 10, 8), {1: "vermelho", 2: "verde", 3: "verde"}) + ciclo(
        datetime(2026, 10, 1), {1: "verde", 2: "verde", 3: "verde"}
    )
    r = _saude(hist, PILARES, REGUAS)
    assert r["status_geral"]["pela_regra_atual"] == "vermelho"
    assert r["status_anterior"] == "verde"
    assert r["algum_vermelho"] is True
    assert r["total_ciclos"] == 2


def test_pilar_novo_sem_cor_deixa_o_status_pendente():
    hist = ciclo(datetime(2026, 10, 1), {1: "verde", 2: "verde"})
    r = _saude(hist, PILARES, REGUAS)
    assert r["status_geral"] is None
    assert r["pilares"]["3"] is None
    # O ciclo incompleto não entra na tendência.
    assert r["status_anterior"] is None


def test_persistencia_conta_avaliacoes_seguidas_na_mesma_cor():
    """§7: cliente amarelo há 3 avaliações, cronograma acabou de ficar
    vermelho (1), escopo verde há 3 (verde nunca é alerta)."""
    hist = (
        ciclo(datetime(2026, 10, 15), {1: "vermelho", 2: "amarelo", 3: "verde"})
        + ciclo(datetime(2026, 10, 8), {1: "verde", 2: "amarelo", 3: "verde"})
        + ciclo(datetime(2026, 10, 1), {1: "verde", 2: "amarelo", 3: "verde"})
    )
    r = _saude(hist, PILARES, REGUAS, {"amarelo": 2, "vermelho": 2})
    assert r["pilares"]["2"]["sequencia"] == 3 and r["pilares"]["2"]["persistente"] is True
    assert r["pilares"]["1"]["sequencia"] == 1 and r["pilares"]["1"]["persistente"] is False
    assert r["pilares"]["3"]["sequencia"] == 3 and r["pilares"]["3"]["persistente"] is False
    assert r["alertas_persistentes"] == 1


def test_limite_de_persistencia_vem_da_configuracao():
    hist = ciclo(datetime(2026, 10, 8), {1: "amarelo", 2: "verde", 3: "verde"}) + ciclo(
        datetime(2026, 10, 1), {1: "amarelo", 2: "verde", 3: "verde"}
    )
    assert _saude(hist, PILARES, REGUAS, {"amarelo": 2, "vermelho": 2})["pilares"]["1"]["persistente"] is True
    assert _saude(hist, PILARES, REGUAS, {"amarelo": 3, "vermelho": 2})["pilares"]["1"]["persistente"] is False
