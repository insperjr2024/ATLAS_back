from datetime import date
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.repositories.semestre_repository import SemestreRepository


class CreatePdiPastaRequest(BaseModel):
    nome: str
    tipo: str  # "inicial" | "encontro"
    prazo: date


def serializar_pasta(pasta, semestre_repository: Optional[SemestreRepository] = None) -> dict:
    # O semestre não é um campo da pasta — é derivado do prazo contra a
    # gestão vigente naquela data, só pra dar contexto no nome ("Encontro 1
    # (2026.2)") sem precisar cadastrar isso manualmente.
    semestre = semestre_repository.get_por_data(pasta.prazo) if semestre_repository else None
    return {
        "id": pasta.id,
        "nome": pasta.nome,
        "tipo": pasta.tipo,
        "prazo": pasta.prazo,
        "ordem": pasta.ordem,
        "semestre": semestre.nome if semestre else None,
    }


class CreatePdiPastaUseCase:
    """A pasta é global — vale pra todo mundo, não por mentorado (regra do
    PDI: a lista de etapas é a mesma pra todo consultor com mentor). `ordem`
    entra automática, sempre depois da última — quem quer reordenar edita
    manualmente na tela de gestão."""

    def __init__(self, db: Session):
        self.repository = DesempenhoPdiPastaRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, request: CreatePdiPastaRequest) -> dict:
        pasta = self.repository.create(
            nome=request.nome,
            tipo=request.tipo,
            prazo=request.prazo,
            ordem=self.repository.get_proxima_ordem(),
        )
        return serializar_pasta(pasta, self.semestre_repository)
