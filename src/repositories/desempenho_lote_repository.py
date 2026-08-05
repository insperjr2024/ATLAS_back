from typing import List

from src.models.desempenho_lote_model import DesempenhoLoteModel
from src.repositories.base_repository import BaseRepository
from src.utils.desempenho_lote import esta_aberto


class DesempenhoLoteRepository(BaseRepository[DesempenhoLoteModel]):
    model = DesempenhoLoteModel

    def get_abertos_agora(self) -> List[DesempenhoLoteModel]:
        return [
            lote
            for lote in self.get_all()
            if esta_aberto(lote.override_manual, lote.data_inicio, lote.data_fim)
        ]
