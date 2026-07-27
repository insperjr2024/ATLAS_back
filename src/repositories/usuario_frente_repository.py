from sqlalchemy.orm import Session
from src.models.usuario_frente_model import UsuarioFrenteModel
from typing import List, Optional


class UsuarioFrenteRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, usuario_id: int, frente_id: int) -> UsuarioFrenteModel:
        usuario_frente = UsuarioFrenteModel(usuario_id=usuario_id, frente_id=frente_id)
        self.db.add(usuario_frente)
        self.db.commit()
        self.db.refresh(usuario_frente)
        return usuario_frente

    def get_by_id(self, usuario_frente_id: int) -> Optional[UsuarioFrenteModel]:
        return self.db.query(UsuarioFrenteModel).filter(UsuarioFrenteModel.id == usuario_frente_id).first()

    def get_by_usuario(self, usuario_id: int) -> List[UsuarioFrenteModel]:
        return self.db.query(UsuarioFrenteModel).filter(UsuarioFrenteModel.usuario_id == usuario_id).all()

    def get_all(self) -> List[UsuarioFrenteModel]:
        return self.db.query(UsuarioFrenteModel).all()