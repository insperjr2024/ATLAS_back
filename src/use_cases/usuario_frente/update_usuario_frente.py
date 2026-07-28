from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository


class UpdateUsuarioFrenteRequest(BaseModel):
    usuario_id: Optional[int] = None
    frente_id: Optional[int] = None


class UpdateUsuarioFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioFrenteRepository(db)

    def execute(self, usuario_frente_id: int, request: UpdateUsuarioFrenteRequest):
        data = request.dict(exclude_unset=True)
        uf = self.repository.update(usuario_frente_id, **data)
        if not uf:
            return None
        return {"id": uf.id, "usuario_id": uf.usuario_id, "frente_id": uf.frente_id}


class DeleteUsuarioFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioFrenteRepository(db)

    def execute(self, usuario_frente_id: int) -> bool:
        return self.repository.delete(usuario_frente_id)