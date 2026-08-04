from sqlalchemy.orm import Session
from src.repositories.semestre_repository import SemestreRepository
from src.use_cases.semestre.get_semestre import serializar_semestre
from src.utils.exceptions import RegraDeNegocioError
from pydantic import BaseModel
from datetime import date
from typing import Literal


class CreateSemestreRequest(BaseModel):
    nome: str
    inicio: date
    fim: date
    status: Literal["ativa", "arquivada"] = "ativa"


class CreateSemestreUseCase:
    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self, request: CreateSemestreRequest):
        if request.fim < request.inicio:
            raise RegraDeNegocioError("O fim do semestre não pode ser anterior ao início")

        # Abrir uma gestão nova arquiva a anterior (§12).
        if request.status == "ativa":
            for outro in self.repository.get_all():
                if outro.status == "ativa":
                    self.repository.update(outro.id, status="arquivada")

        semestre = self.repository.create(
            nome=request.nome,
            inicio=request.inicio,
            fim=request.fim,
            status=request.status,
        )
        return serializar_semestre(semestre)