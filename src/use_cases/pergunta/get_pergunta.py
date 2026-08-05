from sqlalchemy.orm import Session
from src.repositories.pergunta_repository import PerguntaRepository


class GetPerguntaUseCase:
    def __init__(self, db: Session):
        self.repository = PerguntaRepository(db)

    def execute(self, pergunta_id: int):
        pergunta = self.repository.get_by_id(pergunta_id)
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


class ListPerguntasUseCase:
    def __init__(self, db: Session):
        self.repository = PerguntaRepository(db)

    def execute(self):
        perguntas = self.repository.get_all()
        return [
            {
                "id": p.id,
                "formulario_id": p.formulario_id,
                "texto": p.texto,
                "ordem": p.ordem,
                "tipo_resposta": p.tipo_resposta,
                "escopo_id": p.escopo_id,
            }
            for p in perguntas
        ]