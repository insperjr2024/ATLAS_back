from sqlalchemy.orm import Session

from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository


class DeletePdiPastaUseCase:
    """A FK de `desempenho_pdi_envio.pasta_id` sem `ondelete=CASCADE` faz o
    MySQL recusar apagar uma pasta que já tem envio — `BaseRepository.delete`
    já traduz isso em `ResourceInUseError`, que o router converte pra 409.
    Só pastas vazias (criadas por engano) saem de verdade."""

    def __init__(self, db: Session):
        self.repository = DesempenhoPdiPastaRepository(db)

    def execute(self, pasta_id: int) -> bool:
        return self.repository.delete(pasta_id)
