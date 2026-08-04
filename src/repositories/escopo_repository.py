from typing import List

from src.models.escopo_model import EscopoModel
from src.repositories.base_repository import BaseRepository


class EscopoRepository(BaseRepository[EscopoModel]):
    model = EscopoModel

    def get_by_frente(self, frente_id: int) -> List[EscopoModel]:
        return self.filter_by(frente_id=frente_id)

    def get_ativos(self) -> List[EscopoModel]:
        return self.filter_by(ativo=True)