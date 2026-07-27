from sqlalchemy.orm import Session
from src.repositories.cargo_repository import CargoRepository
from pydantic import BaseModel


class CreateCargoRequest(BaseModel):
    nome: str
    categoria_banca: str
    pode_definir_formulario: bool = False
    pode_agendar_banca: bool = False
    pode_gerenciar_cargos: bool = False


class CreateCargoUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self, request: CreateCargoRequest):
        cargo = self.repository.create(
            nome=request.nome,
            categoria_banca=request.categoria_banca,
            pode_definir_formulario=request.pode_definir_formulario,
            pode_agendar_banca=request.pode_agendar_banca,
            pode_gerenciar_cargos=request.pode_gerenciar_cargos
        )
        return {
            "id": cargo.id,
            "nome": cargo.nome,
            "categoria_banca": cargo.categoria_banca
        }