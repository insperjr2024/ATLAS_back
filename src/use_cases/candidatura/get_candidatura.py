from sqlalchemy.orm import Session
from src.repositories.candidatura_repository import CandidaturaRepository


class GetCandidaturaUseCase:
    def __init__(self, db: Session):
        self.repository = CandidaturaRepository(db)

    def execute(self, candidatura_id: int):
        candidatura = self.repository.get_by_id(candidatura_id)
        if not candidatura:
            return None
        return {
            "id": candidatura.id,
            "banca_id": candidatura.banca_id,
            "usuario_id": candidatura.usuario_id,
            "criado_em": candidatura.criado_em,
            "confirmado": candidatura.confirmado
        }


class ListCandidaturasUseCase:
    def __init__(self, db: Session):
        self.repository = CandidaturaRepository(db)

    def execute(self):
        candidaturas = self.repository.get_all()
        return [
            {
                "id": c.id,
                "banca_id": c.banca_id,
                "usuario_id": c.usuario_id,
                "criado_em": c.criado_em,
                "confirmado": c.confirmado
            }
            for c in candidaturas
        ]