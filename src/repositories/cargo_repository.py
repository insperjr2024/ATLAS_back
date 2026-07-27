from sqlalchemy.orm import Session
from src.models.cargo_model import CargoModel
from typing import List, Optional


class CargoRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome: str, categoria_banca: str, pode_definir_formulario: bool,
               pode_agendar_banca: bool, pode_gerenciar_cargos: bool) -> CargoModel:
        cargo = CargoModel(
            nome=nome,
            categoria_banca=categoria_banca,
            pode_definir_formulario=pode_definir_formulario,
            pode_agendar_banca=pode_agendar_banca,
            pode_gerenciar_cargos=pode_gerenciar_cargos
        )
        self.db.add(cargo)
        self.db.commit()
        self.db.refresh(cargo)
        return cargo

    def get_by_id(self, cargo_id: int) -> Optional[CargoModel]:
        return self.db.query(CargoModel).filter(CargoModel.id == cargo_id).first()

    def get_all(self) -> List[CargoModel]:
        return self.db.query(CargoModel).all()