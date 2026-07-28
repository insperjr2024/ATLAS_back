from sqlalchemy.orm import Session
from src.repositories.escopo_repository import EscopoRepository


class GetEscopoUseCase:
    def __init__(self, db: Session):
        self.repository = EscopoRepository(db)

    def execute(self, escopo_id: int):
        escopo = self.repository.get_by_id(escopo_id)
        if not escopo:
            return None
        return {"id": escopo.id, "nome": escopo.nome}


class ListEscoposUseCase:
    def __init__(self, db: Session):
        self.repository = EscopoRepository(db)

    def execute(self):
        escopos = self.repository.get_all()
        return [{"id": e.id, "nome": e.nome} for e in escopos]