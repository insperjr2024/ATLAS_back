from sqlalchemy.orm import Session
from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal


class CreateAvaliacaoNotaRequest(BaseModel):
    avaliacao_id: int
    pergunta_id: int
    nota: Optional[Decimal] = None
    resposta_texto: Optional[str] = None


class CreateAvaliacaoNotaUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoNotaRepository(db)

    def execute(self, request: CreateAvaliacaoNotaRequest):
        avaliacao_nota = self.repository.create(
            avaliacao_id=request.avaliacao_id,
            pergunta_id=request.pergunta_id,
            nota=request.nota,
            resposta_texto=request.resposta_texto
        )
        return {
            "id": avaliacao_nota.id,
            "avaliacao_id": avaliacao_nota.avaliacao_id,
            "pergunta_id": avaliacao_nota.pergunta_id,
            "nota": avaliacao_nota.nota,
            "resposta_texto": avaliacao_nota.resposta_texto
        }