from sqlalchemy.orm import Session

from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository


class DeleteDesempenhoLoteUseCase:
    """Exclusão de verdade — por decisão explícita do time, contrariando a
    regra 2.6 do doc (que só previa `fechar`). Continua protegido pela FK: as
    tabelas `desempenho_avaliacao` e `desempenho_lote_finalizado` apontam pra
    `lote_id` sem `ondelete=CASCADE`, então o MySQL recusa apagar um lote que
    já tem avaliação ou finalização real — só lotes vazios (ex.: sobras de
    teste) saem. `BaseRepository.delete` já traduz isso em
    `ResourceInUseError`, que o router converte pra 409."""

    def __init__(self, db: Session):
        self.repository = DesempenhoLoteRepository(db)

    def execute(self, lote_id: int) -> bool:
        return self.repository.delete(lote_id)
