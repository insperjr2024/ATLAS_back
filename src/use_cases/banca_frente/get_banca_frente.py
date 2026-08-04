from sqlalchemy.orm import Session
from src.repositories.banca_frente_repository import BancaFrenteRepository


class GetBancaFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = BancaFrenteRepository(db)

    def execute(self, banca_frente_id: int):
        bf = self.repository.get_by_id(banca_frente_id)
        if not bf:
            return None
        return {"id": bf.id, "banca_id": bf.banca_id, "frente_id": bf.frente_id}


class ListBancasFrentesUseCase:
    def __init__(self, db: Session):
        self.repository = BancaFrenteRepository(db)

    def execute(self):
        registros = self.repository.get_all()
        return [{"id": r.id, "banca_id": r.banca_id, "frente_id": r.frente_id} for r in registros]