from sqlalchemy.orm import Session
from src.models.semestre_model import SemestreModel
from typing import List, Optional
from datetime import date


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