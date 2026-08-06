from typing import List

from src.models.desempenho_pdi_pasta_model import DesempenhoPdiPastaModel
from src.repositories.base_repository import BaseRepository


class DesempenhoPdiPastaRepository(BaseRepository[DesempenhoPdiPastaModel]):
    model = DesempenhoPdiPastaModel

    def get_ordenadas(self) -> List[DesempenhoPdiPastaModel]:
        return self.db.query(self.model).order_by(self.model.ordem, self.model.id).all()

    def get_proxima_ordem(self) -> int:
        maior = self.db.query(self.model).order_by(self.model.ordem.desc()).first()
        return (maior.ordem + 1) if maior else 1
