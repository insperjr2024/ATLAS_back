from typing import List

from src.models.health_track_regra_model import HealthTrackRegraModel
from src.repositories.base_repository import BaseRepository


class HealthTrackRegraRepository(BaseRepository[HealthTrackRegraModel]):
    model = HealthTrackRegraModel

    def get_versoes(self) -> List[HealthTrackRegraModel]:
        """Todas as versões, da mais antiga para a mais nova. São poucas (uma
        por edição da diretoria), então quem calcula status carrega todas de
        uma vez em vez de consultar uma por ciclo."""
        return (
            self.db.query(HealthTrackRegraModel)
            .order_by(HealthTrackRegraModel.vigente_desde, HealthTrackRegraModel.id)
            .all()
        )
