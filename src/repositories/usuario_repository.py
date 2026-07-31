from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.models.usuario_model import UsuarioModel
from src.utils.exceptions import ResourceInUseError
from typing import List, Optional


class UsuarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome: str, email_insper: str, cargo_id: int,
               senha_hash: str, ativo: bool = True) -> UsuarioModel:
        usuario = UsuarioModel(
            nome=nome,
            email_insper=email_insper,
            cargo_id=cargo_id,
            senha_hash=senha_hash,
            ativo=ativo
        )
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def get_by_id(self, usuario_id: int) -> Optional[UsuarioModel]:
        return self.db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()

    def get_by_email_insper(self, email_insper: str) -> Optional[UsuarioModel]:
        return self.db.query(UsuarioModel).filter(UsuarioModel.email_insper == email_insper).first()

    def get_all(self) -> List[UsuarioModel]:
        return self.db.query(UsuarioModel).all()

    def update(self, usuario_id: int, **kwargs) -> Optional[UsuarioModel]:
        usuario = self.get_by_id(usuario_id)
        if not usuario:
            return None
        for key, value in kwargs.items():
            setattr(usuario, key, value)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def delete(self, usuario_id: int) -> bool:
        usuario = self.get_by_id(usuario_id)
        if not usuario:
            return False
        try:
            self.db.delete(usuario)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()