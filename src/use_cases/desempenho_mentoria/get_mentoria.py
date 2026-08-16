from sqlalchemy.orm import Session

from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository
from src.repositories.usuario_repository import UsuarioRepository


def serializar_mentoria(mentoria, usuarios: dict) -> dict:
    mentor = usuarios.get(mentoria.mentor_id)
    mentorado = usuarios.get(mentoria.mentorado_id)
    return {
        "id": mentoria.id,
        "mentor_id": mentoria.mentor_id,
        "mentor_nome": mentor.nome if mentor else None,
        "mentor_foto": mentor.foto if mentor else None,
        "mentorado_id": mentoria.mentorado_id,
        "mentorado_nome": mentorado.nome if mentorado else None,
        "mentorado_foto": mentorado.foto if mentorado else None,
    }


class ListMentoriasUseCase:
    def __init__(self, db: Session):
        self.repository = DesempenhoMentoriaRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self) -> list[dict]:
        mentorias = self.repository.get_all()
        usuarios = {u.id: u for u in self.usuario_repo.get_all()}
        return [serializar_mentoria(m, usuarios) for m in mentorias]


class GetMentoradosDeUseCase:
    def __init__(self, db: Session):
        self.repository = DesempenhoMentoriaRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self, mentor_id: int) -> list[dict]:
        vinculos = self.repository.get_mentorados_de(mentor_id)
        usuarios = {u.id: u for u in self.usuario_repo.get_all()}
        return [serializar_mentoria(v, usuarios) for v in vinculos]
