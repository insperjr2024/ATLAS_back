from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.cargo_repository import CargoRepository
from src.use_cases.cargo.get_cargo import serializar_cargo


class UpdateCargoRequest(BaseModel):
    nome: Optional[str] = None
    pode_definir_formulario: Optional[bool] = None
    pode_agendar_banca: Optional[bool] = None
    pode_gerenciar_cargos: Optional[bool] = None
    pode_gerenciar_membros: Optional[bool] = None
    pode_gerenciar_nucleo: Optional[bool] = None
    pode_gerenciar_desempenho: Optional[bool] = None
    pode_definir_formulario_desempenho: Optional[bool] = None


class UpdateCargoUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self, cargo_id: int, request: UpdateCargoRequest):
        data = request.model_dump(exclude_unset=True)
        cargo = self.repository.update(cargo_id, **data)
        if not cargo:
            return None
        return serializar_cargo(cargo)


class DeleteCargoUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self, cargo_id: int) -> bool:
        return self.repository.delete(cargo_id)
