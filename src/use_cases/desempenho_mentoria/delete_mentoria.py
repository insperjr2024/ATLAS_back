from sqlalchemy.orm import Session

from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository


class DeleteMentoriaUseCase:
    def __init__(self, db: Session):
        self.repository = DesempenhoMentoriaRepository(db)

    def execute(self, mentoria_id: int) -> bool:
        return self.repository.delete(mentoria_id)
