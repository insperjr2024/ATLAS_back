from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.candidatura_repository import CandidaturaRepository


class UpdateCandidaturaRequest(BaseModel):
    banca_id: Optional[int] = None
    usuario_id: Optional[int] = None
    categoria: Optional[str] = None
    criado_em: Optional[datetime] = None
    confirmado: Optional[bool] = None


class UpdateCandidaturaUseCase:
    def __init__(self, db: Session):
        self.repository = CandidaturaRepository(db)

    def execute(self, candidatura_id: int, request: UpdateCandidaturaRequest):
        data = request.dict(exclude_unset=True)
        candidatura = self.repository.update(candidatura_id, **data)
        if not candidatura:
            return None
        return {
            "id": candidatura.id,
            "banca_id": candidatura.banca_id,
            "usuario_id": candidatura.usuario_id,
            "categoria": candidatura.categoria,
            "criado_em": candidatura.criado_em,
            "confirmado": candidatura.confirmado
        }


class DeleteCandidaturaUseCase:
    def __init__(self, db: Session):
        self.repository = CandidaturaRepository(db)

    def execute(self, candidatura_id: int) -> bool:
        return self.repository.delete(candidatura_id)