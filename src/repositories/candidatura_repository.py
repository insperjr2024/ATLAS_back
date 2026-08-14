from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.models.candidatura_model import CandidaturaModel
from src.utils.exceptions import ResourceInUseError
from typing import List, Optional
from datetime import datetime


class CandidaturaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, banca_id: int, usuario_id: int,
               criado_em: datetime, confirmado: bool = False) -> CandidaturaModel:
        candidatura = CandidaturaModel(
            banca_id=banca_id,
            usuario_id=usuario_id,
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

    def get_by_banca(self, banca_id: int) -> List[CandidaturaModel]:
        return self.db.query(CandidaturaModel).filter(CandidaturaModel.banca_id == banca_id).all()

    def get_by_bancas(self, banca_ids: List[int]) -> List[CandidaturaModel]:
        """As candidaturas de VÁRIAS bancas, numa consulta só.

        Existe para a fila de Aprovações: ela precisa do eleitorado de cada
        banca sem resultado para dizer "1 de 2 votaram", e chamar
        `get_by_banca` num laço é uma consulta por banca.
        """
        if not banca_ids:
            return []
        return (
            self.db.query(CandidaturaModel)
            .filter(CandidaturaModel.banca_id.in_(banca_ids))
            .all()
        )

    def get_by_usuario(self, usuario_id: int) -> List[CandidaturaModel]:
        return self.db.query(CandidaturaModel).filter(CandidaturaModel.usuario_id == usuario_id).all()

    def update(self, candidatura_id: int, **kwargs) -> Optional[CandidaturaModel]:
        candidatura = self.get_by_id(candidatura_id)
        if not candidatura:
            return None
        for key, value in kwargs.items():
            setattr(candidatura, key, value)
        self.db.commit()
        self.db.refresh(candidatura)
        return candidatura

    def delete(self, candidatura_id: int) -> bool:
        candidatura = self.get_by_id(candidatura_id)
        if not candidatura:
            return False
        try:
            self.db.delete(candidatura)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()