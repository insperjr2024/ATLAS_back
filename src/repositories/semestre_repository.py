from sqlalchemy.orm import Session
from src.models.semestre_model import SemestreModel
from typing import List, Optional
from datetime import date
from sqlalchemy.exc import IntegrityError
from src.utils.exceptions import ResourceInUseError


class SemestreRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome: str, inicio: date, fim: date) -> SemestreModel:
        semestre = SemestreModel(nome=nome, inicio=inicio, fim=fim)
        self.db.add(semestre)
        self.db.commit()
        self.db.refresh(semestre)
        return semestre

    def get_by_id(self, semestre_id: int) -> Optional[SemestreModel]:
        return self.db.query(SemestreModel).filter(SemestreModel.id == semestre_id).first()

    def get_all(self) -> List[SemestreModel]:
        return self.db.query(SemestreModel).all()

    def update(self, semestre_id: int, **kwargs) -> Optional[SemestreModel]:
        semestre = self.get_by_id(semestre_id)
        if not semestre:
            return None
        for key, value in kwargs.items():
            setattr(semestre, key, value)
        self.db.commit()
        self.db.refresh(semestre)
        return semestre

    def delete(self, semestre_id: int) -> bool:
        semestre = self.get_by_id(semestre_id)
        if not semestre:
            return False
        try:
            self.db.delete(semestre)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()