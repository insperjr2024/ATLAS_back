from typing import Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository
from src.repositories.pergunta_repository import PerguntaRepository
from src.utils.validacao_nota import validar_avaliacao_nota
from src.utils.exceptions import RegraDeNegocioError


class UpdateAvaliacaoNotaRequest(BaseModel):
    avaliacao_id: Optional[int] = None
    pergunta_id: Optional[int] = None
    nota: Optional[Decimal] = None
    resposta_texto: Optional[str] = None


class UpdateAvaliacaoNotaUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoNotaRepository(db)
        self.pergunta_repository = PerguntaRepository(db)

    def execute(self, avaliacao_nota_id: int, request: UpdateAvaliacaoNotaRequest):
        existente = self.repository.get_by_id(avaliacao_nota_id)
        if not existente:
            return None

        data = request.dict(exclude_unset=True)

        pergunta_id = data.get("pergunta_id", existente.pergunta_id)
        nota = data.get("nota", existente.nota)
        resposta_texto = data.get("resposta_texto", existente.resposta_texto)

        pergunta = self.pergunta_repository.get_by_id(pergunta_id)
        if not pergunta:
            raise RegraDeNegocioError("Pergunta não encontrada")

        validar_avaliacao_nota(pergunta, nota, resposta_texto)

        nota_atualizada = self.repository.update(avaliacao_nota_id, **data)
        return {
            "id": nota_atualizada.id,
            "avaliacao_id": nota_atualizada.avaliacao_id,
            "pergunta_id": nota_atualizada.pergunta_id,
            "nota": nota_atualizada.nota,
            "resposta_texto": nota_atualizada.resposta_texto
        }


class DeleteAvaliacaoNotaUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoNotaRepository(db)

    def execute(self, avaliacao_nota_id: int) -> bool:
        return self.repository.delete(avaliacao_nota_id)