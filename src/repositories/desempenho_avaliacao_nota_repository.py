from typing import List

from src.models.desempenho_avaliacao_nota_model import DesempenhoAvaliacaoNotaModel
from src.repositories.base_repository import BaseRepository


class DesempenhoAvaliacaoNotaRepository(BaseRepository[DesempenhoAvaliacaoNotaModel]):
    model = DesempenhoAvaliacaoNotaModel

    def get_by_avaliacao(self, avaliacao_id: int) -> List[DesempenhoAvaliacaoNotaModel]:
        return self.filter_by(avaliacao_id=avaliacao_id)

    def get_by_avaliacoes(self, avaliacao_ids: List[int]) -> List[DesempenhoAvaliacaoNotaModel]:
        if not avaliacao_ids:
            return []
        return (
            self.db.query(DesempenhoAvaliacaoNotaModel)
            .filter(DesempenhoAvaliacaoNotaModel.avaliacao_id.in_(avaliacao_ids))
            .all()
        )
