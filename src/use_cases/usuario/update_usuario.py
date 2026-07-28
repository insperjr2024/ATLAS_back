from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.usuario_repository import UsuarioRepository


class UpdateUsuarioRequest(BaseModel):
    nome: Optional[str] = None
    email_insper: Optional[str] = None
    cargo_id: Optional[int] = None
    ativo: Optional[bool] = None


class UpdateUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, usuario_id: int, request: UpdateUsuarioRequest):
        data = request.dict(exclude_unset=True)
        usuario = self.repository.update(usuario_id, **data)
        if not usuario:
            return None
        return {
            "id": usuario.id,
            "nome": usuario.nome,
            "email_insper": usuario.email_insper,
            "cargo_id": usuario.cargo_id,
            "ativo": usuario.ativo
        }


class DeleteUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, usuario_id: int) -> bool:
        return self.repository.delete(usuario_id)