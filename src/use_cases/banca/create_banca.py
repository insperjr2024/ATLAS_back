from sqlalchemy.orm import Session
from src.repositories.banca_repository import BancaRepository
from src.utils.banca_status import calcular_status_banca
from pydantic import BaseModel
from datetime import datetime


class CreateBancaRequest(BaseModel):
    nome_projeto: str
    escopo_id: int
    coordenador_id: int
    data_hora: datetime


class CreateBancaUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, request: CreateBancaRequest):
        banca = self.repository.create(
            nome_projeto=request.nome_projeto,
            escopo_id=request.escopo_id,
            coordenador_id=request.coordenador_id,
            data_hora=request.data_hora
        )
        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "escopo_id": banca.escopo_id,
            "coordenador_id": banca.coordenador_id,
            "data_hora": banca.data_hora,
            "status": calcular_status_banca(banca.data_hora),
            "nota_final": None
        }