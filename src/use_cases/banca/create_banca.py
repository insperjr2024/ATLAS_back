from sqlalchemy.orm import Session
from src.repositories.banca_repository import BancaRepository
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CreateBancaRequest(BaseModel):
    nome_projeto: str
    escopo_id: int
    coordenador_id: int
    status: str
    data_hora: Optional[datetime] = None


class CreateBancaUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, request: CreateBancaRequest):
        banca = self.repository.create(
            nome_projeto=request.nome_projeto,
            escopo_id=request.escopo_id,
            coordenador_id=request.coordenador_id,
            status=request.status,
            data_hora=request.data_hora
        )
        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "escopo_id": banca.escopo_id,
            "coordenador_id": banca.coordenador_id,
            "status": banca.status,
            "data_hora": banca.data_hora
        }