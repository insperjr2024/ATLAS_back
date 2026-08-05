from typing import List

from src.models.desempenho_criterio_model import DesempenhoCriterioModel
from src.models.desempenho_formulario_secao_model import DesempenhoFormularioSecaoModel
from src.repositories.base_repository import BaseRepository


class DesempenhoCriterioRepository(BaseRepository[DesempenhoCriterioModel]):
    model = DesempenhoCriterioModel

    def get_by_secao(self, secao_id: int) -> List[DesempenhoCriterioModel]:
        return (
            self.db.query(DesempenhoCriterioModel)
            .filter(DesempenhoCriterioModel.secao_id == secao_id)
            .order_by(DesempenhoCriterioModel.ordem)
            .all()
        )

    def get_by_formulario(self, formulario_id: int) -> List[DesempenhoCriterioModel]:
        return (
            self.db.query(DesempenhoCriterioModel)
            .join(DesempenhoFormularioSecaoModel, DesempenhoFormularioSecaoModel.id == DesempenhoCriterioModel.secao_id)
            .filter(DesempenhoFormularioSecaoModel.formulario_id == formulario_id)
            .all()
        )
