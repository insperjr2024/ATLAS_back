from datetime import date
from typing import Optional

from src.models.semestre_model import SemestreModel
from src.repositories.base_repository import BaseRepository


class SemestreRepository(BaseRepository[SemestreModel]):
    model = SemestreModel

    def get_ativo(self) -> Optional[SemestreModel]:
        return self.first_by(status="ativa")

    def get_por_data(self, data: date) -> Optional[SemestreModel]:
        return (
            self.db.query(SemestreModel)
            .filter(SemestreModel.inicio <= data, SemestreModel.fim >= data)
            .first()
        )