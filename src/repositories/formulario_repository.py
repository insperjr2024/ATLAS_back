from sqlalchemy.orm import Session
from src.models.formulario_model import FormularioModel
from typing import List, Optional


class FormularioRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, semestre_id: int, ativo: bool = True) -> FormularioModel:
        formulario = FormularioModel(semestre_id=semestre_id, ativo=ativo)
        self.db.add(formulario)
        self.db.commit()
        self.db.refresh(formulario)
        return formulario

    def get_by_id(self, formulario_id: int) -> Optional[FormularioModel]:
        return self.db.query(FormularioModel).filter(FormularioModel.id == formulario_id).first()

    def get_all(self) -> List[FormularioModel]:
        return self.db.query(FormularioModel).all()