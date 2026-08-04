from sqlalchemy.orm import Session
from src.repositories.banca_frente_repository import BancaFrenteRepository
from pydantic import BaseModel


class CreateBancaFrenteRequest(BaseModel):
    banca_id: int
    frente_id: int


class CreateBancaFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = BancaFrenteRepository(db)

    def execute(self, request: CreateBancaFrenteRequest):
        banca_frente = self.repository.create(
            banca_id=request.banca_id,
            frente_id=request.frente_id
        )
        return {
            "id": banca_frente.id,
            "banca_id": banca_frente.banca_id,
            "frente_id": banca_frente.frente_id
        }