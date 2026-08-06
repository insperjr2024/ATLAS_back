from typing import List

from src.models.desempenho_formulario_secao_model import DesempenhoFormularioSecaoModel
from src.repositories.base_repository import BaseRepository


class DesempenhoFormularioSecaoRepository(BaseRepository[DesempenhoFormularioSecaoModel]):
    model = DesempenhoFormularioSecaoModel

    def get_by_formulario(self, formulario_id: int) -> List[DesempenhoFormularioSecaoModel]:
        return (
            self.db.query(DesempenhoFormularioSecaoModel)
            .filter(DesempenhoFormularioSecaoModel.formulario_id == formulario_id)
            .order_by(DesempenhoFormularioSecaoModel.ordem)
            .all()
        )
