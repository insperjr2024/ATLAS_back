from sqlalchemy.orm import Session

from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository
from src.repositories.usuario_repository import UsuarioRepository


def serializar_mentoria(mentoria, nomes: dict) -> dict:
    return {
        "id": mentoria.id,
        "mentor_id": mentoria.mentor_id,
        "mentor_nome": nomes.get(mentoria.mentor_id),
        "mentorado_id": mentoria.mentorado_id,
        "mentorado_nome": nomes.get(mentoria.mentorado_id),
    }


class ListMentoriasUseCase:
    def __init__(self, db: Session):
        self.repository = DesempenhoMentoriaRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self) -> list[dict]:
        mentorias = self.repository.get_all()
        nomes = {u.id: u.nome for u in self.usuario_repo.get_all()}
        return [serializar_mentoria(m, nomes) for m in mentorias]


class GetMentoradosDeUseCase:
    def __init__(self, db: Session):
        self.repository = DesempenhoMentoriaRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self, mentor_id: int) -> list[dict]:
        vinculos = self.repository.get_mentorados_de(mentor_id)
        nomes = {u.id: u.nome for u in self.usuario_repo.get_all()}
        return [serializar_mentoria(v, nomes) for v in vinculos]
