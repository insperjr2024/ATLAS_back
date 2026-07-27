from sqlalchemy.orm import Session
from src.repositories.usuario_repository import UsuarioRepository
from pydantic import BaseModel


class CreateUsuarioRequest(BaseModel):
    nome: str
    email_insper: str
    cargo_id: int
    ativo: bool = True


class CreateUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, request: CreateUsuarioRequest):
        usuario = self.repository.create(
            nome=request.nome,
            email_insper=request.email_insper,
            cargo_id=request.cargo_id,
            ativo=request.ativo
        )
        return {
            "id": usuario.id,
            "nome": usuario.nome,
            "email_insper": usuario.email_insper,
            "cargo_id": usuario.cargo_id,
            "ativo": usuario.ativo
        }