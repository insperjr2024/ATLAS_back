from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.frente_repository import FrenteRepository


class UpdateFrenteRequest(BaseModel):
    nome: Optional[str] = None


class UpdateFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = FrenteRepository(db)

    def execute(self, frente_id: int, request: UpdateFrenteRequest):
        data = request.dict(exclude_unset=True)
        frente = self.repository.update(frente_id, **data)
        if not frente:
            return None
        return {"id": frente.id, "nome": frente.nome}


class DeleteFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = FrenteRepository(db)

    def execute(self, frente_id: int) -> bool:
        return self.repository.delete(frente_id)