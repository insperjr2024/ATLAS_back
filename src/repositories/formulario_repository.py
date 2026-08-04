from sqlalchemy.orm import Session
from src.models.formulario_model import FormularioModel
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from src.utils.exceptions import ResourceInUseError


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

    def update(self, formulario_id: int, **kwargs) -> Optional[FormularioModel]:
        formulario = self.get_by_id(formulario_id)
        if not formulario:
            return None
        for key, value in kwargs.items():
            setattr(formulario, key, value)
        self.db.commit()
        self.db.refresh(formulario)
        return formulario

    def delete(self, formulario_id: int) -> bool:
        formulario = self.get_by_id(formulario_id)
        if not formulario:
            return False
        try:
            self.db.delete(formulario)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()