from sqlalchemy.orm import Session
from src.repositories.semestre_repository import SemestreRepository
from pydantic import BaseModel
from datetime import date


class CreateSemestreRequest(BaseModel):
    nome: str
    inicio: date
    fim: date


class CreateSemestreUseCase:
    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self, request: CreateSemestreRequest):
        semestre = self.repository.create(
            nome=request.nome,
            inicio=request.inicio,
            fim=request.fim,
        )
        return {
            "id": semestre.id,
            "nome": semestre.nome,
            "inicio": semestre.inicio,
            "fim": semestre.fim
        }