from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.escopo_repository import EscopoRepository
from src.use_cases.escopo.get_escopo import serializar_escopo


class CreateEscopoRequest(BaseModel):
    nome: str
    frente_id: Optional[int] = None
    ativo: bool = True


class CreateEscopoUseCase:
    def __init__(self, db: Session):
        self.repository = EscopoRepository(db)

    def execute(self, request: CreateEscopoRequest):
        escopo = self.repository.create(
            nome=request.nome,
            frente_id=request.frente_id,
            ativo=request.ativo,
        )
        return serializar_escopo(escopo)
