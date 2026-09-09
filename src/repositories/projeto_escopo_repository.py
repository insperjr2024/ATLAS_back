from typing import List

from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.repositories.base_repository import BaseRepository


class ProjetoEscopoRepository(BaseRepository[ProjetoEscopoModel]):
    model = ProjetoEscopoModel

    def get_by_projeto(self, projeto_id: int) -> List[ProjetoEscopoModel]:
        # `id` só desempata: quem tem o mesmo `ordem` (todo mundo, antes de
        # alguém reordenar manualmente) mantém a ordem de criação de sempre.
        return (
            self.db.query(ProjetoEscopoModel)
            .filter(ProjetoEscopoModel.projeto_id == projeto_id)
            .order_by(ProjetoEscopoModel.ordem, ProjetoEscopoModel.id)
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

    def get_by_ids(self, ids: List[int]) -> List[ProjetoEscopoModel]:
        """Vários escopos vendidos de uma vez, por id — para traduzir os ids
        que `banca_escopo` guarda no `escopo_id` do catálogo sem um
        `get_by_id` por linha na listagem de bancas."""
        if not ids:
            return []
        return (
            self.db.query(ProjetoEscopoModel)
            .filter(ProjetoEscopoModel.id.in_(ids))
            .all()
        )
