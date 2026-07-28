from sqlalchemy.orm import Session
from src.models.escopo_model import EscopoModel
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from src.utils.exceptions import ResourceInUseError


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

    def update(self, escopo_id: int, **kwargs) -> Optional[EscopoModel]:
        escopo = self.get_by_id(escopo_id)
        if not escopo:
            return None
        for key, value in kwargs.items():
            setattr(escopo, key, value)
        self.db.commit()
        self.db.refresh(escopo)
        return escopo

    def delete(self, escopo_id: int) -> bool:
        escopo = self.get_by_id(escopo_id)
        if not escopo:
            return False
        try:
            self.db.delete(escopo)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()