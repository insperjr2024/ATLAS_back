from sqlalchemy.orm import Session
from src.repositories.candidatura_repository import CandidaturaRepository
from pydantic import BaseModel
from datetime import datetime


class CreateCandidaturaRequest(BaseModel):
    banca_id: int
    usuario_id: int
    categoria: str
    criado_em: datetime
    confirmado: bool = False


class CreateCandidaturaUseCase:
    def __init__(self, db: Session):
        self.repository = CandidaturaRepository(db)

    def execute(self, request: CreateCandidaturaRequest):
        candidatura = self.repository.create(
            banca_id=request.banca_id,
            usuario_id=request.usuario_id,
            categoria=request.categoria,
            criado_em=request.criado_em,
            confirmado=request.confirmado
        )
        return {
            "id": candidatura.id,
            "banca_id": candidatura.banca_id,
            "usuario_id": candidatura.usuario_id,
            "categoria": candidatura.categoria,
            "criado_em": candidatura.criado_em,
            "confirmado": candidatura.confirmado
        }