from src.models.projeto_model import ProjetoModel
from src.repositories.base_repository import BaseRepository


class ProjetoRepository(BaseRepository[ProjetoModel]):
    model = ProjetoModel
