from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.cargo_repository import CargoRepository


class UpdateCargoRequest(BaseModel):
    nome: Optional[str] = None
    pode_definir_formulario: Optional[bool] = None
    pode_agendar_banca: Optional[bool] = None
    pode_gerenciar_cargos: Optional[bool] = None


class UpdateCargoUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self, cargo_id: int, request: UpdateCargoRequest):
        data = request.dict(exclude_unset=True)
        cargo = self.repository.update(cargo_id, **data)
        if not cargo:
            return None
        return {
            "id": cargo.id,
            "nome": cargo.nome,
            "pode_definir_formulario": cargo.pode_definir_formulario,
            "pode_agendar_banca": cargo.pode_agendar_banca,
            "pode_gerenciar_cargos": cargo.pode_gerenciar_cargos
        }


class DeleteCargoUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self, cargo_id: int) -> bool:
        return self.repository.delete(cargo_id)