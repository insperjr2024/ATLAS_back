from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from src.repositories.frente_repository import FrenteRepository
from src.use_cases.frente.get_frente import serializar_frente


class UpdateFrenteRequest(BaseModel):
    nome: Optional[str] = None
    ativa: Optional[bool] = None
    piso_banca: Optional[int] = Field(default=None, ge=0)


class UpdateFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = FrenteRepository(db)

    def execute(self, frente_id: int, request: UpdateFrenteRequest):
        data = request.model_dump(exclude_unset=True)
        frente = self.repository.update(frente_id, **data)
        if not frente:
            return None
        return serializar_frente(frente)


class DeleteFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = FrenteRepository(db)

    def execute(self, frente_id: int) -> bool:
        return self.repository.delete(frente_id)