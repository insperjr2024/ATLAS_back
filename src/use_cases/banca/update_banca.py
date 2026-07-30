from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.banca_repository import BancaRepository
from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.banca_nota import calcular_nota_final


class UpdateBancaRequest(BaseModel):
    nome_projeto: Optional[str] = None
    escopo_id: Optional[int] = None
    coordenador_id: Optional[int] = None
    data_hora: Optional[datetime] = None


class UpdateBancaUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)
        self.avaliacao_nota_repository = AvaliacaoNotaRepository(db)

    def execute(self, banca_id: int, request: UpdateBancaRequest):
        data = request.dict(exclude_unset=True)
        banca = self.repository.update(banca_id, **data)
        if not banca:
            return None
        notas = self.avaliacao_nota_repository.get_by_banca(banca_id)
        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "escopo_id": banca.escopo_id,
            "coordenador_id": banca.coordenador_id,
            "data_hora": banca.data_hora,
            "status": calcular_status_banca(banca.data_hora),
            "nota_final": calcular_nota_final(notas)
        }


class DeleteBancaUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int) -> bool:
        return self.repository.delete(banca_id)