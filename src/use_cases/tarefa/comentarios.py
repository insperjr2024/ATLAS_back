"""Comentários de uma tarefa, e quem pode editá-la.

**Quem edita a tarefa**: a diretoria e quem criou. Todo o resto da equipe
continua podendo MOVER a tarefa no kanban — o §3 dá isso aos quatro perfis, e
travar o arrasto quebraria o board como ferramenta de time. O que fica
protegido é o conteúdo: título, responsável e prazo.

**Quem comenta**: quem enxerga o projeto. Discutir uma tarefa é trabalho de
equipe; travar no autor faria o campo não servir para nada.
"""

from typing import List, Optional
from src.middlewares.authorization import eh_diretoria_de_projetos

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.tarefa_comentario_model import TarefaComentarioModel
from src.repositories.base_repository import BaseRepository
from src.repositories.tarefa_repository import TarefaRepository
from src.utils.exceptions import RegraDeNegocioError


class TarefaComentarioRepository(BaseRepository[TarefaComentarioModel]):
    model = TarefaComentarioModel

    def get_by_tarefa(self, tarefa_id: int) -> List[TarefaComentarioModel]:
        return (
            self.db.query(TarefaComentarioModel)
            .filter(TarefaComentarioModel.tarefa_id == tarefa_id)
            .order_by(TarefaComentarioModel.criado_em)
            .all()
        )


def pode_editar_tarefa(tarefa, current_user) -> bool:
    """A diretoria e quem criou a tarefa.

    Mover no kanban NÃO passa por aqui — só a edição de conteúdo.
    """
    return (
        eh_diretoria_de_projetos(current_user)
        or tarefa.criado_por == current_user.id
    )


def exigir_permissao_de_edicao(tarefa, current_user) -> None:
    if not pode_editar_tarefa(tarefa, current_user):
        raise RegraDeNegocioError(
            "Só a diretoria e quem criou a tarefa podem editá-la. "
            "Mover entre colunas continua liberado para a equipe."
        )


def serializar_comentario(comentario) -> dict:
    return {
        "id": comentario.id,
        "tarefa_id": comentario.tarefa_id,
        "autor_id": comentario.autor_id,
        "texto": comentario.texto,
        "criado_em": comentario.criado_em,
    }


class ComentarioRequest(BaseModel):
    texto: str


class ListComentariosUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaComentarioRepository(db)

    def execute(self, tarefa_id: int) -> List[dict]:
        return [serializar_comentario(c) for c in self.repository.get_by_tarefa(tarefa_id)]


class CreateComentarioUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaComentarioRepository(db)
        self.tarefa_repository = TarefaRepository(db)

    def execute(self, tarefa_id: int, request: ComentarioRequest, autor_id: int):
        if not self.tarefa_repository.get_by_id(tarefa_id):
            return None
        texto = (request.texto or "").strip()
        if not texto:
            raise RegraDeNegocioError("O comentário não pode ser vazio")

        comentario = self.repository.create(
            tarefa_id=tarefa_id, autor_id=autor_id, texto=texto
        )
        return serializar_comentario(comentario)


class DeleteComentarioUseCase:
    """Apagar é do autor — e da diretoria."""

    def __init__(self, db: Session):
        self.repository = TarefaComentarioRepository(db)

    def execute(self, comentario_id: int, current_user) -> Optional[bool]:
        comentario = self.repository.get_by_id(comentario_id)
        if not comentario:
            return None
        eh_diretor_projetos = eh_diretoria_de_projetos(current_user)
        if comentario.autor_id != current_user.id and not eh_diretor_projetos:
            raise RegraDeNegocioError("Você só pode apagar os próprios comentários")
        return self.repository.delete(comentario_id)
