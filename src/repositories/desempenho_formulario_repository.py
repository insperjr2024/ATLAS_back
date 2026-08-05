from src.models.desempenho_formulario_model import DesempenhoFormularioModel
from src.repositories.base_repository import BaseRepository


class DesempenhoFormularioRepository(BaseRepository[DesempenhoFormularioModel]):
    model = DesempenhoFormularioModel
