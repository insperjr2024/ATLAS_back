from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError


class CreateMentoriaRequest(BaseModel):
    mentor_id: int
    mentorado_id: int


#: Quem pode ser mentor — liderança acima do consultor. Coordenador é o
#: caso comum, mas gerente e diretor também assumem mentorado quando a
#: diretoria decide (2026-08-06).
POSICOES_ELEGIVEIS_MENTOR = ("coordenador", "gerente", "diretor")


class CreateMentoriaUseCase:
    """Elegibilidade de mentor: posição em `POSICOES_ELEGIVEIS_MENTOR` — sem
    tabela de cargo separada. O vínculo em si é sempre escolha manual do
    admin."""

    def __init__(self, db: Session):
        self.repository = DesempenhoMentoriaRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self, request: CreateMentoriaRequest) -> dict:
        if request.mentor_id == request.mentorado_id:
            raise RegraDeNegocioError("Mentor e mentorado não podem ser a mesma pessoa")

        mentor = self.usuario_repo.get_by_id(request.mentor_id)
        if not mentor or mentor.posicao not in POSICOES_ELEGIVEIS_MENTOR:
            raise RegraDeNegocioError("O mentor precisa ser coordenador, gerente ou diretor")

        if self.repository.get_mentor_de(request.mentorado_id):
            raise RegraDeNegocioError("Este mentorado já tem um mentor — remova o vínculo atual primeiro")

        mentoria = self.repository.create(mentor_id=request.mentor_id, mentorado_id=request.mentorado_id)
        return {"id": mentoria.id, "mentor_id": mentoria.mentor_id, "mentorado_id": mentoria.mentorado_id}
