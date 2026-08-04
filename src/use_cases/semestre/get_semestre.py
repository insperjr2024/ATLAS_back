from sqlalchemy.orm import Session
from src.repositories.semestre_repository import SemestreRepository


def serializar_semestre(semestre):
    return {
        "id": semestre.id,
        "nome": semestre.nome,
        "inicio": semestre.inicio,
        "fim": semestre.fim,
        "status": semestre.status,
    }


class GetSemestreUseCase:
    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self, semestre_id: int):
        semestre = self.repository.get_by_id(semestre_id)
        if not semestre:
            return None
        return serializar_semestre(semestre)


class ListSemestresUseCase:
    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self):
        return [serializar_semestre(s) for s in self.repository.get_all()]


class GetSemestreAtivoUseCase:
    """A gestão corrente — é a referência da grade horária, do formulário de
    avaliação e dos indicadores do monitoramento (§12)."""

    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self):
        ativo = next((s for s in self.repository.get_all() if s.status == "ativa"), None)
        return serializar_semestre(ativo) if ativo else None