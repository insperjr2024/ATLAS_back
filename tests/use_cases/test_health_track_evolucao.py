"""`get_evolucao.foto`: a carteira num instante, pela cor vigente de cada
pilar até ali."""

from datetime import datetime
from types import SimpleNamespace

from src.use_cases.health_track.get_evolucao import foto
from src.utils.health_track_status import RegraStatusGeral

REGRA = RegraStatusGeral(verde_max_amarelos=1, verde_max_vermelhos=0, vermelho_min_amarelos=3, vermelho_min_vermelhos=1)
PILARES = [1, 2]


def linhas(em, cores):
    return [SimpleNamespace(pilar_id=p, cor=c, avaliado_em=em) for p, c in cores.items()]


def test_foto_usa_so_o_que_existia_ate_o_instante():
    historico = {
        10: linhas(datetime(2026, 10, 15), {1: "vermelho", 2: "verde"}) + linhas(datetime(2026, 10, 1), {1: "verde", 2: "verde"}),
        11: linhas(datetime(2026, 10, 1), {1: "amarelo"}),
    }
    antes = foto("Rodada 1", datetime(2026, 10, 2), [10, 11], historico, PILARES, REGRA)
    assert antes["verde"] == 1 and antes["vermelho"] == 0
    # 11 só tem um pilar colorido: não entra no status, mas entra no pilar.
    assert antes["avaliados"] == 1 and antes["total"] == 2
    assert antes["pilares"]["1"] == {"verde": 1, "amarelo": 1, "vermelho": 0}

    depois = foto("Hoje", datetime(2026, 10, 20), [10, 11], historico, PILARES, REGRA)
    assert depois["vermelho"] == 1 and depois["verde"] == 0
