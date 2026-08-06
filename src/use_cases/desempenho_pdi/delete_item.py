from sqlalchemy.orm import Session

from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository


class DeletePdiItemUseCase:
    """Mesmo padrão de `DeletePdiPastaUseCase`: a FK de
    `desempenho_pdi_envio.item_id` faz o MySQL recusar apagar um item que já
    tem envio — `BaseRepository.delete` traduz isso em `ResourceInUseError`
    (409, ver router)."""

    def __init__(self, db: Session):
        self.repository = DesempenhoPdiItemRepository(db)

    def execute(self, item_id: int) -> bool:
        return self.repository.delete(item_id)
