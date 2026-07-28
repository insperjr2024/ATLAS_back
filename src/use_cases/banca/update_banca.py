from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.banca_repository import BancaRepository


class UpdateBancaRequest(BaseModel):
    nome_projeto: Optional[str] = None
    escopo_id: Optional[int] = None
    coordenador_id: Optional[int] = None
    data_hora: Optional[datetime] = None
    status: Optional[str] = None
    nota_final: Optional[Decimal] = None


class UpdateBancaUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, request: UpdateBancaRequest):
        data = request.dict(exclude_unset=True)
        banca = self.repository.update(banca_id, **data)
        if not banca:
            return None
        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "escopo_id": banca.escopo_id,
            "coordenador_id": banca.coordenador_id,
            "status": banca.status,
            "data_hora": banca.data_hora,
            "nota_final": banca.nota_final
        }


class DeleteBancaUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int) -> bool:
        return self.repository.delete(banca_id)