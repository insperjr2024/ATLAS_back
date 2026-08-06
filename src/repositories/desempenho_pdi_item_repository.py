from typing import List

from src.models.desempenho_pdi_item_model import DesempenhoPdiItemModel
from src.repositories.base_repository import BaseRepository


class DesempenhoPdiItemRepository(BaseRepository[DesempenhoPdiItemModel]):
    model = DesempenhoPdiItemModel

    def get_da_pasta(self, pasta_id: int) -> List[DesempenhoPdiItemModel]:
        return (
            self.db.query(self.model)
            .filter(self.model.pasta_id == pasta_id)
            .order_by(self.model.ordem, self.model.id)
            .all()
        )

    def get_proxima_ordem(self, pasta_id: int) -> int:
        maior = (
            self.db.query(self.model)
            .filter(self.model.pasta_id == pasta_id)
            .order_by(self.model.ordem.desc())
            .first()
        )
        return (maior.ordem + 1) if maior else 1
