from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository


class UpdateEquipeProjetoRequest(BaseModel):
    banca_id: Optional[int] = None
    usuario_id: Optional[int] = None


class UpdateEquipeProjetoUseCase:
    def __init__(self, db: Session):
        self.repository = EquipeProjetoRepository(db)

    def execute(self, equipe_id: int, request: UpdateEquipeProjetoRequest):
        data = request.dict(exclude_unset=True)
        equipe = self.repository.update(equipe_id, **data)
        if not equipe:
            return None
        return {"id": equipe.id, "banca_id": equipe.banca_id, "usuario_id": equipe.usuario_id}


class DeleteEquipeProjetoUseCase:
    def __init__(self, db: Session):
        self.repository = EquipeProjetoRepository(db)

    def execute(self, equipe_id: int) -> bool:
        return self.repository.delete(equipe_id)