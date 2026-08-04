from sqlalchemy.orm import Session
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from pydantic import BaseModel


class CreateEquipeProjetoRequest(BaseModel):
    banca_id: int
    usuario_id: int


class CreateEquipeProjetoUseCase:
    def __init__(self, db: Session):
        self.repository = EquipeProjetoRepository(db)

    def execute(self, request: CreateEquipeProjetoRequest):
        equipe = self.repository.create(
            banca_id=request.banca_id,
            usuario_id=request.usuario_id
        )
        return {
            "id": equipe.id,
            "banca_id": equipe.banca_id,
            "usuario_id": equipe.usuario_id
        }