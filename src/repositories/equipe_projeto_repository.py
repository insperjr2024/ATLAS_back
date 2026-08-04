from sqlalchemy.orm import Session
from src.models.equipe_projeto_model import EquipeProjetoModel
from typing import List, Optional


class EquipeProjetoRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, banca_id: int, usuario_id: int) -> EquipeProjetoModel:
        equipe = EquipeProjetoModel(banca_id=banca_id, usuario_id=usuario_id)
        self.db.add(equipe)
        self.db.commit()
        self.db.refresh(equipe)
        return equipe

    def get_by_id(self, equipe_id: int) -> Optional[EquipeProjetoModel]:
        return self.db.query(EquipeProjetoModel).filter(EquipeProjetoModel.id == equipe_id).first()

    def get_all(self) -> List[EquipeProjetoModel]:
        return self.db.query(EquipeProjetoModel).all()

    def get_by_banca(self, banca_id: int) -> List[EquipeProjetoModel]:
        return self.db.query(EquipeProjetoModel).filter(EquipeProjetoModel.banca_id == banca_id).all()

    def get_by_usuario(self, usuario_id: int) -> List[EquipeProjetoModel]:
        return self.db.query(EquipeProjetoModel).filter(EquipeProjetoModel.usuario_id == usuario_id).all()

    def update(self, equipe_id: int, **kwargs) -> Optional[EquipeProjetoModel]:
        equipe = self.get_by_id(equipe_id)
        if not equipe:
            return None
        for key, value in kwargs.items():
            setattr(equipe, key, value)
        self.db.commit()
        self.db.refresh(equipe)
        return equipe

    def delete(self, equipe_id: int) -> bool:
        equipe = self.get_by_id(equipe_id)
        if not equipe:
            return False
        self.db.delete(equipe)
        self.db.commit()
        return True