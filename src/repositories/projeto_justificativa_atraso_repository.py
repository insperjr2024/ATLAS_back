from typing import List

from src.models.projeto_justificativa_atraso_model import ProjetoJustificativaAtrasoModel
from src.repositories.base_repository import BaseRepository


class ProjetoJustificativaAtrasoRepository(BaseRepository[ProjetoJustificativaAtrasoModel]):
    model = ProjetoJustificativaAtrasoModel

    def get_by_projeto(self, projeto_id: int) -> List[ProjetoJustificativaAtrasoModel]:
        return (
            self.db.query(self.model)
            .filter(self.model.projeto_id == projeto_id)
            .order_by(self.model.registrado_em)
            .all()
        )

    def get_by_projetos(self, projeto_ids: List[int]) -> List[ProjetoJustificativaAtrasoModel]:
        """Pra montar o aviso "atraso já justificado" da aba Atrasos (§7.4) sem
        uma query por projeto."""
        if not projeto_ids:
            return []
        return (
            self.db.query(self.model)
            .filter(self.model.projeto_id.in_(projeto_ids))
            .order_by(self.model.registrado_em)
            .all()
        )
