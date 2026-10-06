from typing import List

from src.models.health_track_pilar_model import HealthTrackPilarModel
from src.repositories.base_repository import BaseRepository


class HealthTrackPilarRepository(BaseRepository[HealthTrackPilarModel]):
    model = HealthTrackPilarModel

    def get_ativos(self) -> List[HealthTrackPilarModel]:
        """Os pilares em uso, na ordem de exibição. `id` desempata quando a
        diretoria deixar duas ordens iguais — a lista não pode mudar de ordem
        entre uma request e outra."""
        return (
            self.db.query(HealthTrackPilarModel)
            .filter(HealthTrackPilarModel.ativo.is_(True))
            .order_by(HealthTrackPilarModel.ordem, HealthTrackPilarModel.id)
            .all()
        )
