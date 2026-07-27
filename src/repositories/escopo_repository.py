from sqlalchemy.orm import Session
from src.models.escopo_model import EscopoModel
from typing import List, Optional


class EscopoRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome: str) -> EscopoModel:
        escopo = EscopoModel(nome=nome)
        self.db.add(escopo)
        self.db.commit()
        self.db.refresh(escopo)
        return escopo

    def get_by_id(self, escopo_id: int) -> Optional[EscopoModel]:
        return self.db.query(EscopoModel).filter(EscopoModel.id == escopo_id).first()

    def get_all(self) -> List[EscopoModel]:
        return self.db.query(EscopoModel).all()