from sqlalchemy.orm import Session
from src.models.usuario_model import UsuarioModel
from typing import List, Optional


class UsuarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome: str, email_insper: str, cargo_id: int, ativo: bool = True) -> UsuarioModel:
        usuario = UsuarioModel(
            nome=nome,
            email_insper=email_insper,
            cargo_id=cargo_id,
            ativo=ativo
        )
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def get_by_id(self, usuario_id: int) -> Optional[UsuarioModel]:
        return self.db.query(UsuarioModel).filter(UsuarioModel.id == usuario_id).first()

    def get_all(self) -> List[UsuarioModel]:
        return self.db.query(UsuarioModel).all()