from sqlalchemy.orm import Session
from src.repositories.frente_repository import FrenteRepository
from src.use_cases.frente.get_frente import serializar_frente
from pydantic import BaseModel, Field


class CreateFrenteRequest(BaseModel):
    nome: str
    ativa: bool = True
    piso_banca: int = Field(default=1, ge=0)


class CreateFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = FrenteRepository(db)

    def execute(self, request: CreateFrenteRequest):
        frente = self.repository.create(
            nome=request.nome,
            ativa=request.ativa,
            piso_banca=request.piso_banca,
        )
        return serializar_frente(frente)