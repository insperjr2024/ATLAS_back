from sqlalchemy.orm import Session

from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.repositories.semestre_repository import SemestreRepository
from src.use_cases.desempenho_pdi.create_pasta import serializar_pasta


class ListPdiPastasUseCase:
    def __init__(self, db: Session):
        self.repository = DesempenhoPdiPastaRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self) -> list[dict]:
        return [serializar_pasta(p, self.semestre_repository) for p in self.repository.get_ordenadas()]
