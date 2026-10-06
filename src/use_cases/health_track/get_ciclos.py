from itertools import groupby

from sqlalchemy.orm import Session

from src.repositories.health_track_avaliacao_repository import HealthTrackAvaliacaoRepository
from src.repositories.health_track_regra_repository import HealthTrackRegraRepository
from src.use_cases.health_track.serializar import nomes_para, serializar_avaliacao
from src.utils.health_track_status import ReguasStatus, status_geral


class GetCiclosUseCase:
    """O histórico agrupado por preenchimento, cada um com o status geral.

    Um ciclo = as linhas de um mesmo envio, que dividem `avaliado_em` e
    `avaliado_por`. Do mais novo para o mais antigo.

    O status vem pelas duas réguas (`na_epoca` e `pela_regra_atual`, ver
    `utils/health_track_status.py`). O ciclo conta com as cores que tinha
    quando foi preenchido, inclusive de pilar desativado depois — era um
    pilar válido na época.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = HealthTrackAvaliacaoRepository(db)
        self.regra_repo = HealthTrackRegraRepository(db)

    def execute(self, projeto_id: int) -> list[dict]:
        historico = self.repository.get_historico(projeto_id)
        pilares, usuarios = nomes_para(self.db, historico)
        reguas = ReguasStatus(self.regra_repo.get_versoes())

        ciclos = []
        # O histórico já vem ordenado por `avaliado_em` desc, então as linhas
        # de um envio estão juntas.
        for (avaliado_em, avaliado_por), linhas in groupby(
            historico, key=lambda a: (a.avaliado_em, a.avaliado_por)
        ):
            linhas = sorted(linhas, key=lambda a: (_ordem(pilares, a.pilar_id), a.pilar_id))
            avaliador = usuarios.get(avaliado_por)
            ciclos.append({
                "avaliado_em": avaliado_em,
                "avaliado_por": avaliado_por,
                "avaliado_por_nome": avaliador.nome if avaliador else None,
                "status_geral": status_geral([a.cor for a in linhas], avaliado_em, reguas),
                "avaliacoes": [serializar_avaliacao(a, pilares, usuarios) for a in linhas],
            })
        return ciclos


def _ordem(pilares: dict, pilar_id: int) -> int:
    pilar = pilares.get(pilar_id)
    return pilar.ordem if pilar else 0
