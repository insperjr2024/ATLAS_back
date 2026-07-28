from sqlalchemy.orm import Session
from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository


class GetAvaliacaoNotaUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoNotaRepository(db)

    def execute(self, avaliacao_nota_id: int):
        nota = self.repository.get_by_id(avaliacao_nota_id)
        if not nota:
            return None
        return {
            "id": nota.id,
            "avaliacao_id": nota.avaliacao_id,
            "pergunta_id": nota.pergunta_id,
            "nota": nota.nota,
            "resposta_texto": nota.resposta_texto
        }


class ListAvaliacoesNotasUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoNotaRepository(db)

    def execute(self):
        notas = self.repository.get_all()
        return [
            {
                "id": n.id,
                "avaliacao_id": n.avaliacao_id,
                "pergunta_id": n.pergunta_id,
                "nota": n.nota,
                "resposta_texto": n.resposta_texto
            }
            for n in notas
        ]