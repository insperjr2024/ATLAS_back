from sqlalchemy.orm import Session
from src.models.frente_model import FrenteModel
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from src.utils.exceptions import ResourceInUseError


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

    def update(self, frente_id: int, **kwargs) -> Optional[FrenteModel]:
        frente = self.get_by_id(frente_id)
        if not frente:
            return None
        for key, value in kwargs.items():
            setattr(frente, key, value)
        self.db.commit()
        self.db.refresh(frente)
        return frente

    def delete(self, frente_id: int) -> bool:
        frente = self.get_by_id(frente_id)
        if not frente:
            return False
        try:
            self.db.delete(frente)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()