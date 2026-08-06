from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.pergunta_repository import PerguntaRepository


class UpdatePerguntaRequest(BaseModel):
    formulario_id: Optional[int] = None
    texto: Optional[str] = None
    ordem: Optional[int] = None
    tipo_resposta: Optional[str] = None
    escopo_id: Optional[int] = None


class UpdatePerguntaUseCase:
    def __init__(self, db: Session):
        self.repository = PerguntaRepository(db)

    def execute(self, pergunta_id: int, request: UpdatePerguntaRequest):
        data = request.dict(exclude_unset=True)
        pergunta = self.repository.update(pergunta_id, **data)
        if not pergunta:
            return None
        return {
            "id": pergunta.id,
            "formulario_id": pergunta.formulario_id,
            "texto": pergunta.texto,
            "ordem": pergunta.ordem,
            "tipo_resposta": pergunta.tipo_resposta,
            "escopo_id": pergunta.escopo_id,
        }


class DeletePerguntaUseCase:
    def __init__(self, db: Session):
        self.repository = PerguntaRepository(db)

    def execute(self, pergunta_id: int) -> bool:
        return self.repository.delete(pergunta_id)