from sqlalchemy.orm import Session
from src.models.banca_model import BancaModel
from typing import List, Optional
from datetime import datetime


class BancaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome_projeto: str, escopo_id: int, coordenador_id: int,
               status: str, data_hora: Optional[datetime] = None) -> BancaModel:
        banca = BancaModel(
            nome_projeto=nome_projeto,
            escopo_id=escopo_id,
            coordenador_id=coordenador_id,
            status=status,
            data_hora=data_hora
        )
        self.db.add(banca)
        self.db.commit()
        self.db.refresh(banca)
        return banca

    def get_by_id(self, banca_id: int) -> Optional[BancaModel]:
        return self.db.query(BancaModel).filter(BancaModel.id == banca_id).first()

    def get_all(self) -> List[BancaModel]:
        return self.db.query(BancaModel).all()