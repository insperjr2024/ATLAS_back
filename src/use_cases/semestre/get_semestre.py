from sqlalchemy.orm import Session
from src.repositories.semestre_repository import SemestreRepository


class GetSemestreUseCase:
    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self, semestre_id: int):
        semestre = self.repository.get_by_id(semestre_id)
        if not semestre:
            return None
        return {"id": semestre.id, "nome": semestre.nome, "inicio": semestre.inicio, "fim": semestre.fim}


class ListSemestresUseCase:
    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self):
        semestres = self.repository.get_all()
        return [
            {"id": s.id, "nome": s.nome, "inicio": s.inicio, "fim": s.fim}
            for s in semestres
        ]