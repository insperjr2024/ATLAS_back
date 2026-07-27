from sqlalchemy.orm import Session
from src.repositories.frente_repository import FrenteRepository
from pydantic import BaseModel


class CreateFrenteRequest(BaseModel):
    nome: str


class CreateFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = FrenteRepository(db)

    def execute(self, request: CreateFrenteRequest):
        frente = self.repository.create(nome=request.nome)
        return {
            "id": frente.id,
            "nome": frente.nome
        }