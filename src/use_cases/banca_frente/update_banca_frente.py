from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.banca_frente_repository import BancaFrenteRepository


class UpdateBancaFrenteRequest(BaseModel):
    banca_id: Optional[int] = None
    frente_id: Optional[int] = None


class UpdateBancaFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = BancaFrenteRepository(db)

    def execute(self, banca_frente_id: int, request: UpdateBancaFrenteRequest):
        data = request.dict(exclude_unset=True)
        bf = self.repository.update(banca_frente_id, **data)
        if not bf:
            return None
        return {"id": bf.id, "banca_id": bf.banca_id, "frente_id": bf.frente_id}


class DeleteBancaFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = BancaFrenteRepository(db)

    def execute(self, banca_frente_id: int) -> bool:
        return self.repository.delete(banca_frente_id)