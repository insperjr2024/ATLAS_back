from sqlalchemy.orm import Session
from src.models.banca_frente_model import BancaFrenteModel
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from src.utils.exceptions import ResourceInUseError


class BancaFrenteRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, banca_id: int, frente_id: int) -> BancaFrenteModel:
        banca_frente = BancaFrenteModel(banca_id=banca_id, frente_id=frente_id)
        self.db.add(banca_frente)
        self.db.commit()
        self.db.refresh(banca_frente)
        return banca_frente

    def get_by_id(self, banca_frente_id: int) -> Optional[BancaFrenteModel]:
        return self.db.query(BancaFrenteModel).filter(BancaFrenteModel.id == banca_frente_id).first()

    def get_by_banca(self, banca_id: int) -> List[BancaFrenteModel]:
        return self.db.query(BancaFrenteModel).filter(BancaFrenteModel.banca_id == banca_id).all()

    def get_all(self) -> List[BancaFrenteModel]:
        return self.db.query(BancaFrenteModel).all()

    def update(self, banca_frente_id: int, **kwargs) -> Optional[BancaFrenteModel]:
        banca_frente = self.get_by_id(banca_frente_id)
        if not banca_frente:
            return None
        for key, value in kwargs.items():
            setattr(banca_frente, key, value)
        self.db.commit()
        self.db.refresh(banca_frente)
        return banca_frente

    def delete(self, banca_frente_id: int) -> bool:
        banca_frente = self.get_by_id(banca_frente_id)
        if not banca_frente:
            return False
        try:
            self.db.delete(banca_frente)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()