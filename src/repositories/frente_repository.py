from typing import List

from src.models.frente_model import FrenteModel
from src.repositories.base_repository import BaseRepository


class FrenteRepository(BaseRepository[FrenteModel]):
    model = FrenteModel

    def get_ativas(self) -> List[FrenteModel]:
        return self.filter_by(ativa=True)
