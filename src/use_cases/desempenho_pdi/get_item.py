from sqlalchemy.orm import Session

from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository
from src.use_cases.desempenho_pdi.create_item import serializar_item


class ListItensDaPastaUseCase:
    def __init__(self, db: Session):
        self.repository = DesempenhoPdiItemRepository(db)

    def execute(self, pasta_id: int) -> list[dict]:
        return [serializar_item(i) for i in self.repository.get_da_pasta(pasta_id)]
