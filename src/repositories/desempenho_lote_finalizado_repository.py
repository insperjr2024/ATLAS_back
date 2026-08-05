from src.models.desempenho_lote_finalizado_model import DesempenhoLoteFinalizadoModel
from src.repositories.base_repository import BaseRepository


class DesempenhoLoteFinalizadoRepository(BaseRepository[DesempenhoLoteFinalizadoModel]):
    model = DesempenhoLoteFinalizadoModel
