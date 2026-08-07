from typing import List

from src.models.projeto_remarcacao_banca_model import ProjetoRemarcacaoBancaModel
from src.repositories.base_repository import BaseRepository


class ProjetoRemarcacaoBancaRepository(BaseRepository[ProjetoRemarcacaoBancaModel]):
    model = ProjetoRemarcacaoBancaModel

    def get_by_projeto(self, projeto_id: int) -> List[ProjetoRemarcacaoBancaModel]:
        return (
            self.db.query(self.model)
            .filter(self.model.projeto_id == projeto_id)
            .order_by(self.model.registrado_em)
            .all()
        )
