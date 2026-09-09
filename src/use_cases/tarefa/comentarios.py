"""Comentários de uma tarefa, e quem pode editá-la / movê-la.

**Quem edita ou exclui a tarefa** (2026-09-09, a pedido): a **coordenação do
projeto** e a diretoria de projetos. O consultor NÃO edita nem exclui — nem
o que ele mesmo criou (antes "quem criou" também podia; saiu). Conteúdo
protegido: título, responsáveis, prazo.

**Quem move no kanban**: coordenação e diretoria movem qualquer tarefa; o
consultor move só as em que está como **responsável**. Antes o §3 deixava os
quatro perfis moverem qualquer uma.

**Quem comenta**: quem enxerga o projeto. Discutir uma tarefa é trabalho de
equipe; travar no autor faria o campo não servir para nada.
"""

from typing import List, Optional
from src.middlewares.authorization import eh_diretoria_de_projetos

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.tarefa_comentario_model import TarefaComentarioModel
from src.repositories.base_repository import BaseRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.tarefa_repository import TarefaRepository
from src.utils.exceptions import CODIGO_TAREFA_SEM_PERMISSAO, RegraDeNegocioError


class TarefaComentarioRepository(BaseRepository[TarefaComentarioModel]):
    model = TarefaComentarioModel

    def get_by_tarefa(self, tarefa_id: int) -> List[TarefaComentarioModel]:
        return (
            self.db.query(TarefaComentarioModel)
            .filter(TarefaComentarioModel.tarefa_id == tarefa_id)
            .order_by(TarefaComentarioModel.criado_em)
            .all()
        )


def eh_coordenador_do_projeto(db: Session, projeto_id: int, usuario_id: int) -> bool:
    """`projeto_membro.papel == "coordenador"` para esta pessoa neste projeto —
    o papel do PROJETO, não a `usuario.posicao` global."""
    vinculo = ProjetoMembroRepository(db).get_atual_do_usuario_no_projeto(
        projeto_id, usuario_id
    )
    return bool(vinculo and vinculo.papel == "coordenador")


def pode_editar_tarefa(tarefa, current_user, db: Session) -> bool:
    """Editar CONTEÚDO (título, responsáveis, prazo) e EXCLUIR: coordenação do
    projeto e diretoria de projetos. O consultor não mexe — nem no que ele
    mesmo criou (2026-09-09, a pedido).

    Mover no kanban NÃO passa por aqui — ver `pode_mover_tarefa`.
    """
    return (
        eh_diretoria_de_projetos(current_user)
        or eh_coordenador_do_projeto(db, tarefa.projeto_id, current_user.id)
    )


def exigir_permissao_de_edicao(tarefa, current_user, db: Session) -> None:
    if not pode_editar_tarefa(tarefa, current_user, db):
        raise RegraDeNegocioError(
            "Só a coordenação do projeto e a diretoria podem editar ou excluir "
            "uma tarefa. Mover no kanban continua liberado para quem é responsável.",
            codigo=CODIGO_TAREFA_SEM_PERMISSAO,
        )


def pode_mover_tarefa(tarefa, current_user, db: Session, responsavel_ids) -> bool:
    """Arrastar no kanban: coordenação e diretoria movem qualquer tarefa; o
    consultor move só as em que está como responsável (2026-09-09)."""
    if pode_editar_tarefa(tarefa, current_user, db):
        return True
    return current_user is not None and current_user.id in set(responsavel_ids or [])


def exigir_permissao_de_movimento(tarefa, current_user, db: Session, responsavel_ids) -> None:
    if not pode_mover_tarefa(tarefa, current_user, db, responsavel_ids):
        raise RegraDeNegocioError(
            "Você só pode mover tarefas em que está como responsável.",
            codigo=CODIGO_TAREFA_SEM_PERMISSAO,
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
