from typing import List

from src.models.health_track_acao_model import HealthTrackAcaoModel
from src.repositories.base_repository import BaseRepository


class HealthTrackAcaoRepository(BaseRepository[HealthTrackAcaoModel]):
    model = HealthTrackAcaoModel

    def get_by_projeto(self, projeto_id: int) -> List[HealthTrackAcaoModel]:
        """Abertas primeiro (prazo mais perto no topo), concluídas depois."""
        return (
            self.db.query(HealthTrackAcaoModel)
            .filter(HealthTrackAcaoModel.projeto_id == projeto_id)
            .order_by(
                HealthTrackAcaoModel.concluida_em.isnot(None),
                HealthTrackAcaoModel.prazo.is_(None),
                HealthTrackAcaoModel.prazo,
                HealthTrackAcaoModel.id.desc(),
            )
            .all()
        )

    def get_por_responsavel(self, usuario_id: int) -> List[HealthTrackAcaoModel]:
        """As ações de UMA pessoa, abertas primeiro: é o que ela vê no projeto
        dela, sem ter acesso ao Health Track."""
        return (
            self.db.query(HealthTrackAcaoModel)
            .filter(HealthTrackAcaoModel.responsavel_id == usuario_id)
            .order_by(
                HealthTrackAcaoModel.concluida_em.isnot(None),
                HealthTrackAcaoModel.prazo.is_(None),
                HealthTrackAcaoModel.prazo,
                HealthTrackAcaoModel.id.desc(),
            )
            .all()
        )

    def get_abertas(self) -> List[HealthTrackAcaoModel]:
        return (
            self.db.query(HealthTrackAcaoModel)
            .filter(HealthTrackAcaoModel.concluida_em.is_(None))
            .order_by(HealthTrackAcaoModel.prazo.is_(None), HealthTrackAcaoModel.prazo, HealthTrackAcaoModel.id)
            .all()
        )
