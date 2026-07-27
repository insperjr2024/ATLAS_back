from sqlalchemy.orm import Session
from src.repositories.escopo_repository import EscopoRepository
from pydantic import BaseModel


class CreateEscopoRequest(BaseModel):
    nome: str


class CreateEscopoUseCase:
    def __init__(self, db: Session):
        self.repository = EscopoRepository(db)

    def execute(self, request: CreateEscopoRequest):
        escopo = self.repository.create(nome=request.nome)
        return {
            "id": escopo.id,
            "nome": escopo.nome
        }