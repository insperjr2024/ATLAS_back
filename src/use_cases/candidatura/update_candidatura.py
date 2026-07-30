from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.banca_repository import BancaRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError


class UpdateCandidaturaRequest(BaseModel):
    banca_id: Optional[int] = None
    usuario_id: Optional[int] = None
    criado_em: Optional[datetime] = None
    confirmado: Optional[bool] = None


class UpdateCandidaturaUseCase:
    def __init__(self, db: Session):
        self.repository = CandidaturaRepository(db)

    def execute(self, candidatura_id: int, request: UpdateCandidaturaRequest):
        data = request.dict(exclude_unset=True)
        candidatura = self.repository.update(candidatura_id, **data)
        if not candidatura:
            return None
        return {
            "id": candidatura.id,
            "banca_id": candidatura.banca_id,
            "usuario_id": candidatura.usuario_id,
            "criado_em": candidatura.criado_em,
            "confirmado": candidatura.confirmado
        }


class DeleteCandidaturaUseCase:
    def __init__(self, db: Session):
        self.repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, candidatura_id: int) -> bool:
        candidatura = self.repository.get_by_id(candidatura_id)
        if not candidatura:
            return False

        banca = self.banca_repository.get_by_id(candidatura.banca_id)
        if banca and calcular_status_banca(banca.data_hora) == "realizada":
            raise RegraDeNegocioError("Não é possível se desalocar: esta banca já foi realizada")

        return self.repository.delete(candidatura_id)