from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.escopo_repository import EscopoRepository


class UpdateEscopoRequest(BaseModel):
    nome: Optional[str] = None


class UpdateEscopoUseCase:
    def __init__(self, db: Session):
        self.repository = EscopoRepository(db)

    def execute(self, escopo_id: int, request: UpdateEscopoRequest):
        data = request.dict(exclude_unset=True)
        escopo = self.repository.update(escopo_id, **data)
        if not escopo:
            return None
        return {"id": escopo.id, "nome": escopo.nome}


class DeleteEscopoUseCase:
    def __init__(self, db: Session):
        self.repository = EscopoRepository(db)

    def execute(self, escopo_id: int) -> bool:
        return self.repository.delete(escopo_id)