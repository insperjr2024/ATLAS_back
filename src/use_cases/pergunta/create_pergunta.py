from sqlalchemy.orm import Session
from src.repositories.pergunta_repository import PerguntaRepository
from pydantic import BaseModel


class CreatePerguntaRequest(BaseModel):
    formulario_id: int
    texto: str
    ordem: int
    tipo_resposta: str = "nota"


class CreatePerguntaUseCase:
    def __init__(self, db: Session):
        self.repository = PerguntaRepository(db)

    def execute(self, request: CreatePerguntaRequest):
        pergunta = self.repository.create(
            formulario_id=request.formulario_id,
            texto=request.texto,
            ordem=request.ordem,
            tipo_resposta=request.tipo_resposta
        )
        return {
            "id": pergunta.id,
            "formulario_id": pergunta.formulario_id,
            "texto": pergunta.texto,
            "ordem": pergunta.ordem,
            "tipo_resposta": pergunta.tipo_resposta
        }