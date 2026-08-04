from typing import List

from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.repositories.base_repository import BaseRepository


class ProjetoEscopoRepository(BaseRepository[ProjetoEscopoModel]):
    model = ProjetoEscopoModel

    def get_by_projeto(self, projeto_id: int) -> List[ProjetoEscopoModel]:
        return (
            self.db.query(ProjetoEscopoModel)
            .filter(ProjetoEscopoModel.projeto_id == projeto_id)
            .order_by(ProjetoEscopoModel.id)
            .all()
        )

    def get_by_projetos(self, projeto_ids: List[int]) -> List[ProjetoEscopoModel]:
        if not projeto_ids:
            return []
        return (
            self.db.query(ProjetoEscopoModel)
            .filter(ProjetoEscopoModel.projeto_id.in_(projeto_ids))
            .all()
        )
