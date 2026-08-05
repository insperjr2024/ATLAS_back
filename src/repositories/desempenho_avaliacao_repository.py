from typing import List, Optional

from src.models.desempenho_avaliacao_model import DesempenhoAvaliacaoModel
from src.repositories.base_repository import BaseRepository


class DesempenhoAvaliacaoRepository(BaseRepository[DesempenhoAvaliacaoModel]):
    model = DesempenhoAvaliacaoModel

    def get_by_lote(self, lote_id: int) -> List[DesempenhoAvaliacaoModel]:
        return self.filter_by(lote_id=lote_id)

    def get_recebidas_por(self, avaliado_id: int) -> List[DesempenhoAvaliacaoModel]:
        return self.filter_by(avaliado_id=avaliado_id)

    def existe_par(self, lote_id: int, avaliador_id: int, avaliado_id: int) -> bool:
        return (
            self.first_by(lote_id=lote_id, avaliador_id=avaliador_id, avaliado_id=avaliado_id)
            is not None
        )

    def get_par(self, lote_id: int, avaliador_id: int, avaliado_id: int) -> Optional[DesempenhoAvaliacaoModel]:
        return self.first_by(lote_id=lote_id, avaliador_id=avaliador_id, avaliado_id=avaliado_id)
