from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.desempenho_mentoria.get_mentoria import serializar_mentoria
from src.utils.exceptions import RegraDeNegocioError
from src.middlewares.authorization import DIRETORIA, DIRETORIA_DE_PESSOAS, DIRETORIA_DE_PROJETOS


class CreateMentoriaRequest(BaseModel):
    mentor_id: int
    mentorado_id: int


#: Quem pode ser mentor — liderança acima do consultor. Coordenador é o
#: caso comum, mas gerente e diretor também assumem mentorado quando a
#: diretoria decide (2026-08-06).
POSICOES_ELEGIVEIS_MENTOR = ("coordenador", "gerente", *DIRETORIA)


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
        # Mesma forma da listagem, incluindo nome e foto: a tela acrescenta o
        # que volta daqui direto na lista que já está na mão, sem recarregar.
        # Sem eles, o vínculo recém-criado aparecia como uma linha em branco
        # até alguém dar F5.
        mentorado = self.usuario_repo.get_by_id(request.mentorado_id)
        return serializar_mentoria(
            mentoria,
            {mentor.id: mentor, **({mentorado.id: mentorado} if mentorado else {})},
        )
