from sqlalchemy.orm import Session
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from pydantic import BaseModel


class CreateUsuarioFrenteRequest(BaseModel):
    usuario_id: int
    frente_id: int


class CreateUsuarioFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioFrenteRepository(db)

    def execute(self, request: CreateUsuarioFrenteRequest):
        usuario_frente = self.repository.create(
            usuario_id=request.usuario_id,
            frente_id=request.frente_id
        )
        return {
            "id": usuario_frente.id,
            "usuario_id": usuario_frente.usuario_id,
            "frente_id": usuario_frente.frente_id
        }