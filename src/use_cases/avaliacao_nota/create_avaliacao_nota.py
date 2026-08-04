from sqlalchemy.orm import Session
from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository
from src.repositories.pergunta_repository import PerguntaRepository
from src.utils.validacao_nota import validar_avaliacao_nota
from src.utils.exceptions import RegraDeNegocioError
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
        self.pergunta_repository = PerguntaRepository(db)

    def execute(self, request: CreateAvaliacaoNotaRequest):
        pergunta = self.pergunta_repository.get_by_id(request.pergunta_id)
        if not pergunta:
            raise RegraDeNegocioError("Pergunta não encontrada")

        validar_avaliacao_nota(pergunta, request.nota, request.resposta_texto)

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