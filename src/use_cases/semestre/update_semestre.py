from typing import Optional
from datetime import date
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.semestre_repository import SemestreRepository


class UpdateSemestreRequest(BaseModel):
    nome: Optional[str] = None
    inicio: Optional[date] = None
    fim: Optional[date] = None


class UpdateSemestreUseCase:
    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self, semestre_id: int, request: UpdateSemestreRequest):
        data = request.dict(exclude_unset=True)
        semestre = self.repository.update(semestre_id, **data)
        if not semestre:
            return None
        return {"id": semestre.id, "nome": semestre.nome, "inicio": semestre.inicio, "fim": semestre.fim}


class DeleteSemestreUseCase:
    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self, semestre_id: int) -> bool:
        return self.repository.delete(semestre_id)