from sqlalchemy.orm import Session
from src.models.candidatura_model import CandidaturaModel
from typing import List, Optional
from datetime import datetime


class CandidaturaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, banca_id: int, usuario_id: int, categoria: str,
               criado_em: datetime, confirmado: bool = False) -> CandidaturaModel:
        candidatura = CandidaturaModel(
            banca_id=banca_id,
            usuario_id=usuario_id,
            categoria=categoria,
            criado_em=criado_em,
            confirmado=confirmado
        )
        self.db.add(candidatura)
        self.db.commit()
        self.db.refresh(candidatura)
        return candidatura

    def get_by_id(self, candidatura_id: int) -> Optional[CandidaturaModel]:
        return self.db.query(CandidaturaModel).filter(CandidaturaModel.id == candidatura_id).first()

    def get_all(self) -> List[CandidaturaModel]:
        return self.db.query(CandidaturaModel).all()