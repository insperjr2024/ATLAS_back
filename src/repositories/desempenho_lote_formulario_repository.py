from typing import Dict, Optional

from src.models.desempenho_lote_formulario_model import DesempenhoLoteFormularioModel
from src.repositories.base_repository import BaseRepository


class DesempenhoLoteFormularioRepository(BaseRepository[DesempenhoLoteFormularioModel]):
    model = DesempenhoLoteFormularioModel

    def formulario_id_de(self, lote_id: int, papel: str) -> Optional[int]:
        vinculo = self.first_by(lote_id=lote_id, papel=papel)
        return vinculo.formulario_id if vinculo else None

    def papeis_congelados(self, lote_id: int) -> Dict[str, int]:
        return {v.papel: v.formulario_id for v in self.filter_by(lote_id=lote_id)}
