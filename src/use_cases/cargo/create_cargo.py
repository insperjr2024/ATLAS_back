from sqlalchemy.orm import Session
from src.repositories.cargo_repository import CargoRepository
from src.use_cases.cargo.get_cargo import serializar_cargo
from pydantic import BaseModel


class CreateCargoRequest(BaseModel):
    nome: str
    pode_definir_formulario: bool = False
    pode_agendar_banca: bool = False
    pode_gerenciar_cargos: bool = False
    pode_gerenciar_membros: bool = False
    pode_gerenciar_nucleo: bool = False
    pode_gerenciar_desempenho: bool = False
    pode_definir_formulario_desempenho: bool = False


class CreateCargoUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self, request: CreateCargoRequest):
        cargo = self.repository.create(**request.model_dump())
        return serializar_cargo(cargo)
