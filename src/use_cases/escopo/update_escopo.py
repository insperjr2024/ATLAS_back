from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.escopo_repository import EscopoRepository
from src.use_cases.escopo.get_escopo import serializar_escopo


class UpdateEscopoRequest(BaseModel):
    nome: Optional[str] = None
    frente_id: Optional[int] = None
    ativo: Optional[bool] = None


class UpdateEscopoUseCase:
    def __init__(self, db: Session):
        self.repository = EscopoRepository(db)

    def execute(self, escopo_id: int, request: UpdateEscopoRequest):
        data = request.model_dump(exclude_unset=True)
        escopo = self.repository.update(escopo_id, **data)
        if not escopo:
            return None
        return serializar_escopo(escopo)


class DeleteEscopoUseCase:
    def __init__(self, db: Session):
        self.repository = EscopoRepository(db)

    def execute(self, escopo_id: int) -> bool:
        return self.repository.delete(escopo_id)