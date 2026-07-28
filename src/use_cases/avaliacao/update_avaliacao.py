from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.avaliacao_repository import AvaliacaoRepository


class UpdateAvaliacaoRequest(BaseModel):
    banca_id: Optional[int] = None
    avaliador_id: Optional[int] = None
    formulario_id: Optional[int] = None
    status: Optional[str] = None
    comentario_feedback: Optional[str] = None
    submetida_em: Optional[datetime] = None


class UpdateAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoRepository(db)

    def execute(self, avaliacao_id: int, request: UpdateAvaliacaoRequest):
        data = request.dict(exclude_unset=True)
        avaliacao = self.repository.update(avaliacao_id, **data)
        if not avaliacao:
            return None
        return {
            "id": avaliacao.id,
            "banca_id": avaliacao.banca_id,
            "avaliador_id": avaliacao.avaliador_id,
            "formulario_id": avaliacao.formulario_id,
            "status": avaliacao.status,
            "comentario_feedback": avaliacao.comentario_feedback,
            "submetida_em": avaliacao.submetida_em
        }


class DeleteAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoRepository(db)

    def execute(self, avaliacao_id: int) -> bool:
        return self.repository.delete(avaliacao_id)