from typing import List

from src.models.projeto_frente_model import ProjetoFrenteModel
from src.repositories.base_repository import BaseRepository


class ProjetoFrenteRepository(BaseRepository[ProjetoFrenteModel]):
    model = ProjetoFrenteModel

    def get_by_projeto(self, projeto_id: int) -> List[ProjetoFrenteModel]:
        return self.filter_by(projeto_id=projeto_id)

    def get_by_projetos(self, projeto_ids: List[int]) -> List[ProjetoFrenteModel]:
        """Em lote — mesmo padrão de `ProjetoVendedorRepository`/
        `ProjetoMembroRepository`: uma consulta só pra uma tela que lista
        vários projetos, em vez de uma por projeto."""
        if not projeto_ids:
            return []
        return (
            self.db.query(ProjetoFrenteModel)
            .filter(ProjetoFrenteModel.projeto_id.in_(projeto_ids))
            .all()
        )

    def get_by_frente(self, frente_id: int) -> List[ProjetoFrenteModel]:
        return self.filter_by(frente_id=frente_id)

    def delete_by_projeto(self, projeto_id: int) -> None:
        self.db.query(ProjetoFrenteModel).filter(
            ProjetoFrenteModel.projeto_id == projeto_id
        ).delete()
        self.db.commit()
