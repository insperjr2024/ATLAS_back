from typing import Literal, Optional
from datetime import date
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.semestre_repository import SemestreRepository
from src.use_cases.semestre.get_semestre import serializar_semestre
from src.utils.exceptions import RegraDeNegocioError


class UpdateSemestreRequest(BaseModel):
    nome: Optional[str] = None
    inicio: Optional[date] = None
    fim: Optional[date] = None
    status: Optional[Literal["ativa", "arquivada"]] = None


class UpdateSemestreUseCase:
    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self, semestre_id: int, request: UpdateSemestreRequest):
        data = request.model_dump(exclude_unset=True)

        # Só uma gestão ativa por vez: abrir a nova arquiva a anterior (§12).
        if data.get("status") == "ativa":
            for outro in self.repository.get_all():
                if outro.id != semestre_id and outro.status == "ativa":
                    self.repository.update(outro.id, status="arquivada")

        inicio = data.get("inicio")
        fim = data.get("fim")
        if inicio and fim and fim < inicio:
            raise RegraDeNegocioError("O fim do semestre não pode ser anterior ao início")

        semestre = self.repository.update(semestre_id, **data)
        if not semestre:
            return None
        return serializar_semestre(semestre)


class DeleteSemestreUseCase:
    def __init__(self, db: Session):
        self.repository = SemestreRepository(db)

    def execute(self, semestre_id: int) -> bool:
        return self.repository.delete(semestre_id)