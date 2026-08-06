from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_repository import UsuarioRepository


def serializar_usuario(usuario, projetos_alocados: int = 0):
    """`projetos_alocados` é a carga atual da pessoa (§7.3), usada na hora de
    montar a equipe de um projeto. O padrão 0 vale para quem acabou de ser
    cadastrado e ainda não entrou em projeto nenhum."""
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email_insper": usuario.email_insper,
        "cargo_id": usuario.cargo_id,
        "posicao": usuario.posicao,
        "status": usuario.status,
        "ativo": usuario.ativo,
        "semestre_graduacao": usuario.semestre_graduacao,
        "projetos_alocados": projetos_alocados,
    }


class GetUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(self, usuario_id: int):
        usuario = self.repository.get_by_id(usuario_id)
        if not usuario:
            return None
        alocados = self.membro_repository.contar_ativos_por_usuario()
        return serializar_usuario(usuario, alocados.get(usuario.id, 0))


class ListUsuariosUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(self, posicao: Optional[str] = None, apenas_ativos: bool = False):
        """Quem some da lista: o `desligado` (§10). O `ex_membro` continua
        aparecendo, porque o histórico dele precisa ficar íntegro."""
        usuarios = [u for u in self.repository.get_all() if u.status != "desligado"]
        if posicao:
            usuarios = [u for u in usuarios if u.posicao == posicao]
        if apenas_ativos:
            usuarios = [u for u in usuarios if u.status == "ativo"]
        # Uma consulta agregada para a lista inteira, não uma por pessoa.
        alocados = self.membro_repository.contar_ativos_por_usuario()
        return [serializar_usuario(u, alocados.get(u.id, 0)) for u in usuarios]