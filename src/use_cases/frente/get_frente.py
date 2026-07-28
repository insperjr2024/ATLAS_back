from sqlalchemy.orm import Session
from src.repositories.frente_repository import FrenteRepository


class GetFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = FrenteRepository(db)

    def execute(self, frente_id: int):
        frente = self.repository.get_by_id(frente_id)
        if not frente:
            return None
        return {"id": frente.id, "nome": frente.nome}


class ListFrentesUseCase:
    def __init__(self, db: Session):
        self.repository = FrenteRepository(db)

    def execute(self):
        frentes = self.repository.get_all()
        return [{"id": f.id, "nome": f.nome} for f in frentes]