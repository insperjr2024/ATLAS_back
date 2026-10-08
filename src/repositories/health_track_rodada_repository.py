from typing import List, Optional

from src.models.health_track_rodada_model import HealthTrackRodadaModel, HealthTrackRodadaProjetoModel
from src.repositories.base_repository import BaseRepository


class HealthTrackRodadaRepository(BaseRepository[HealthTrackRodadaModel]):
    model = HealthTrackRodadaModel

    def get_aberta(self) -> Optional[HealthTrackRodadaModel]:
        """A rodada em andamento. Uma por vez, por regra do use case."""
        return (
            self.db.query(HealthTrackRodadaModel)
            .filter(HealthTrackRodadaModel.concluida_em.is_(None))
            .order_by(HealthTrackRodadaModel.id.desc())
            .first()
        )

    def get_todas(self) -> List[HealthTrackRodadaModel]:
        return self.db.query(HealthTrackRodadaModel).order_by(HealthTrackRodadaModel.id.desc()).all()


class HealthTrackRodadaProjetoRepository(BaseRepository[HealthTrackRodadaProjetoModel]):
    model = HealthTrackRodadaProjetoModel

    def get_by_rodada(self, rodada_id: int) -> List[HealthTrackRodadaProjetoModel]:
        return (
            self.db.query(HealthTrackRodadaProjetoModel)
            .filter(HealthTrackRodadaProjetoModel.rodada_id == rodada_id)
            .order_by(HealthTrackRodadaProjetoModel.id)
            .all()
        )

    def get_by_rodadas(self, rodada_ids: List[int]) -> List[HealthTrackRodadaProjetoModel]:
        if not rodada_ids:
            return []
        return (
            self.db.query(HealthTrackRodadaProjetoModel)
            .filter(HealthTrackRodadaProjetoModel.rodada_id.in_(rodada_ids))
            .all()
        )

    def get_item(self, rodada_id: int, projeto_id: int) -> Optional[HealthTrackRodadaProjetoModel]:
        return (
            self.db.query(HealthTrackRodadaProjetoModel)
            .filter(
                HealthTrackRodadaProjetoModel.rodada_id == rodada_id,
                HealthTrackRodadaProjetoModel.projeto_id == projeto_id,
            )
            .first()
        )
