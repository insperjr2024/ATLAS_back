from sqlalchemy.orm import Session
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository


class GetEquipeProjetoUseCase:
    def __init__(self, db: Session):
        self.repository = EquipeProjetoRepository(db)

    def execute(self, equipe_id: int):
        equipe = self.repository.get_by_id(equipe_id)
        if not equipe:
            return None
        return {"id": equipe.id, "banca_id": equipe.banca_id, "usuario_id": equipe.usuario_id}


class ListEquipesProjetoUseCase:
    def __init__(self, db: Session):
        self.repository = EquipeProjetoRepository(db)

    def execute(self):
        equipes = self.repository.get_all()
        return [{"id": e.id, "banca_id": e.banca_id, "usuario_id": e.usuario_id} for e in equipes]