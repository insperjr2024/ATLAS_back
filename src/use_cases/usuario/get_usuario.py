from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.usuario_repository import UsuarioRepository


def serializar_usuario(usuario):
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email_insper": usuario.email_insper,
        "cargo_id": usuario.cargo_id,
        "posicao": usuario.posicao,
        "status": usuario.status,
        "ativo": usuario.ativo,
    }


class GetUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, usuario_id: int):
        usuario = self.repository.get_by_id(usuario_id)
        if not usuario:
            return None
        return serializar_usuario(usuario)


class ListUsuariosUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, posicao: Optional[str] = None, apenas_ativos: bool = False):
        """Quem some da lista: o `desligado` (§10). O `ex_membro` continua
        aparecendo, porque o histórico dele precisa ficar íntegro."""
        usuarios = [u for u in self.repository.get_all() if u.status != "desligado"]
        if posicao:
            usuarios = [u for u in usuarios if u.posicao == posicao]
        if apenas_ativos:
            usuarios = [u for u in usuarios if u.status == "ativo"]
        return [serializar_usuario(u) for u in usuarios]