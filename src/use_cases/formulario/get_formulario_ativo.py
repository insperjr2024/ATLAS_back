from sqlalchemy.orm import Session
from src.repositories.formulario_repository import FormularioRepository
from src.repositories.pergunta_repository import PerguntaRepository


class GetFormularioAtivoUseCase:
    def __init__(self, db: Session):
        self.repository = FormularioRepository(db)
        self.pergunta_repository = PerguntaRepository(db)

    def execute(self):
        formularios = self.repository.get_all()
        ativo = next((f for f in formularios if f.ativo), None)
        if not ativo:
            return None
        perguntas = self.pergunta_repository.get_by_formulario(ativo.id)
        return {
            "id": ativo.id,
            "semestre_id": ativo.semestre_id,
            "perguntas": [
                {
                    "id": p.id,
                    "texto": p.texto,
                    "ordem": p.ordem,
                    "tipo_resposta": p.tipo_resposta
                }
                for p in perguntas
            ]
        }