from typing import List

from src.models.cronograma_etapa_model import CronogramaEtapaModel, CronogramaMarcoModel
from src.repositories.base_repository import BaseRepository


class CronogramaEtapaRepository(BaseRepository[CronogramaEtapaModel]):
    model = CronogramaEtapaModel

    def get_by_escopo(self, projeto_escopo_id: int) -> List[CronogramaEtapaModel]:
        return (
            self.db.query(CronogramaEtapaModel)
            .filter(CronogramaEtapaModel.projeto_escopo_id == projeto_escopo_id)
            .order_by(CronogramaEtapaModel.ordem, CronogramaEtapaModel.data_inicio)
            .all()
        )

    def get_by_escopos(self, escopo_ids: List[int]) -> List[CronogramaEtapaModel]:
        if not escopo_ids:
            return []
        return (
            self.db.query(CronogramaEtapaModel)
            .filter(CronogramaEtapaModel.projeto_escopo_id.in_(escopo_ids))
            .order_by(CronogramaEtapaModel.ordem, CronogramaEtapaModel.data_inicio)
            .all()
        )

    def proxima_ordem(self, projeto_escopo_id: int) -> int:
        etapas = self.get_by_escopo(projeto_escopo_id)
        return max((e.ordem for e in etapas), default=-1) + 1


class CronogramaMarcoRepository(BaseRepository[CronogramaMarcoModel]):
    model = CronogramaMarcoModel

    def get_by_projeto(self, projeto_id: int) -> List[CronogramaMarcoModel]:
        return (
            self.db.query(CronogramaMarcoModel)
            .filter(CronogramaMarcoModel.projeto_id == projeto_id)
            .order_by(CronogramaMarcoModel.data)
            .all()
        )
