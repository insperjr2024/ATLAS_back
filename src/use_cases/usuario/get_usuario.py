from sqlalchemy.orm import Session
from src.repositories.usuario_repository import UsuarioRepository


class GetUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, usuario_id: int):
        usuario = self.repository.get_by_id(usuario_id)
        if not usuario:
            return None
        return {
            "id": usuario.id,
            "nome": usuario.nome,
            "email_insper": usuario.email_insper,
            "cargo_id": usuario.cargo_id,
            "ativo": usuario.ativo
        }


class ListUsuariosUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self):
        usuarios = self.repository.get_all()
        return [
            {
                "id": u.id,
                "nome": u.nome,
                "email_insper": u.email_insper,
                "cargo_id": u.cargo_id,
                "ativo": u.ativo
            }
            for u in usuarios
        ]