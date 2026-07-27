from sqlalchemy.orm import Session
from src.models.frente_model import FrenteModel
from typing import List, Optional


class FrenteRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome: str) -> FrenteModel:
        frente = FrenteModel(nome=nome)
        self.db.add(frente)
        self.db.commit()
        self.db.refresh(frente)
        return frente

    def get_by_id(self, frente_id: int) -> Optional[FrenteModel]:
        return self.db.query(FrenteModel).filter(FrenteModel.id == frente_id).first()

    def get_all(self) -> List[FrenteModel]:
        return self.db.query(FrenteModel).all()