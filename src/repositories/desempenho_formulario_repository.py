from typing import List, Optional

from src.models.desempenho_formulario_model import DesempenhoFormularioModel
from src.repositories.base_repository import BaseRepository


class DesempenhoFormularioRepository(BaseRepository[DesempenhoFormularioModel]):
    model = DesempenhoFormularioModel

    def vigente(self, tipo: str, papel: str) -> Optional[DesempenhoFormularioModel]:
        return self.first_by(tipo=tipo, papel=papel, vigente=True)

    def get_por_papel(self, papel: str) -> List[DesempenhoFormularioModel]:
        """Vigentes E congelados: relatório e listagem precisam reconhecer
        a Avaliação do Escopo de qualquer versão."""
        return self.filter_by(papel=papel)
