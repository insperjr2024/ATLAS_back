from sqlalchemy.orm import Session
from src.repositories.avaliacao_repository import AvaliacaoRepository


class GetAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoRepository(db)

    def execute(self, avaliacao_id: int):
        avaliacao = self.repository.get_by_id(avaliacao_id)
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


class ListAvaliacoesUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoRepository(db)

    def execute(self):
        avaliacoes = self.repository.get_all()
        return [
            {
                "id": a.id,
                "banca_id": a.banca_id,
                "avaliador_id": a.avaliador_id,
                "formulario_id": a.formulario_id,
                "status": a.status,
                "comentario_feedback": a.comentario_feedback,
                "submetida_em": a.submetida_em
            }
            for a in avaliacoes
        ]