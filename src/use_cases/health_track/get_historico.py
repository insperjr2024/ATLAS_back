from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.health_track_avaliacao_repository import HealthTrackAvaliacaoRepository
from src.use_cases.health_track.serializar import nomes_para, serializar_avaliacao


class GetHistoricoUseCase:
    """Todas as avaliações do projeto, da mais nova para a mais antiga.

    Inclui pilares hoje desativados: o histórico é o que foi avaliado na
    época, não o que existe agora.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = HealthTrackAvaliacaoRepository(db)

    def execute(self, projeto_id: int, pilar_id: Optional[int] = None) -> list[dict]:
        historico = self.repository.get_historico(projeto_id, pilar_id)
        pilares, usuarios = nomes_para(self.db, historico)
        return [serializar_avaliacao(a, pilares, usuarios) for a in historico]
