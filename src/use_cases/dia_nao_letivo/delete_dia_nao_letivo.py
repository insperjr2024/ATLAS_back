from sqlalchemy.orm import Session

from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository


class DeleteDiaNaoLetivoUseCase:
    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)

    def execute(self, dia_id: int) -> bool:
        return self.repository.delete(dia_id)


class DeleteDiasNaoLetivosDoSemestreUseCase:
    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)

    def execute(self, semestre_id: int) -> int:
        return self.repository.delete_por_semestre(semestre_id)
