from sqlalchemy.orm import Session
from src.repositories.avaliacao_repository import AvaliacaoRepository
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CreateAvaliacaoRequest(BaseModel):
    banca_id: int
    avaliador_id: int
    formulario_id: int
    status: str = "rascunho"
    comentario_feedback: Optional[str] = None
    submetida_em: Optional[datetime] = None


class CreateAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoRepository(db)

    def execute(self, request: CreateAvaliacaoRequest):
        avaliacao = self.repository.create(
            banca_id=request.banca_id,
            avaliador_id=request.avaliador_id,
            formulario_id=request.formulario_id,
            status=request.status,
            comentario_feedback=request.comentario_feedback,
            submetida_em=request.submetida_em
        )
        return {
            "id": avaliacao.id,
            "banca_id": avaliacao.banca_id,
            "avaliador_id": avaliacao.avaliador_id,
            "formulario_id": avaliacao.formulario_id,
            "status": avaliacao.status
        }