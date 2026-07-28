from typing import Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository


class UpdateAvaliacaoNotaRequest(BaseModel):
    avaliacao_id: Optional[int] = None
    pergunta_id: Optional[int] = None
    nota: Optional[Decimal] = None
    resposta_texto: Optional[str] = None


class UpdateAvaliacaoNotaUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoNotaRepository(db)

    def execute(self, avaliacao_nota_id: int, request: UpdateAvaliacaoNotaRequest):
        data = request.dict(exclude_unset=True)
        nota = self.repository.update(avaliacao_nota_id, **data)
        if not nota:
            return None
        return {
            "id": nota.id,
            "avaliacao_id": nota.avaliacao_id,
            "pergunta_id": nota.pergunta_id,
            "nota": nota.nota,
            "resposta_texto": nota.resposta_texto
        }


class DeleteAvaliacaoNotaUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoNotaRepository(db)

    def execute(self, avaliacao_nota_id: int) -> bool:
        return self.repository.delete(avaliacao_nota_id)