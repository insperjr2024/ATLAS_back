from sqlalchemy.orm import Session

from src.repositories.desempenho_avaliacao_repository import DesempenhoAvaliacaoRepository


class DeleteDesempenhoAvaliacaoUseCase:
    """Remove uma avaliação específica (correção de admin, ex.: resposta
    enviada por engano) — `desempenho_avaliacao_nota` cai junto via CASCADE.
    Diferente de `desempenho_lote`, que nunca tem DELETE (regra 2.6): aqui é
    uma única submissão, não uma rodada inteira, e não deixa nada órfão."""

    def __init__(self, db: Session):
        self.repository = DesempenhoAvaliacaoRepository(db)

    def execute(self, avaliacao_id: int) -> bool:
        return self.repository.delete(avaliacao_id)
