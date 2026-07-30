from sqlalchemy.orm import Session
from src.models.cargo_model import CargoModel
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from src.utils.exceptions import ResourceInUseError


class CargoRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome: str, pode_definir_formulario: bool,
               pode_agendar_banca: bool, pode_gerenciar_cargos: bool) -> CargoModel:
        cargo = CargoModel(
            nome=nome,
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

    def update(self, cargo_id: int, **kwargs) -> Optional[CargoModel]:
        cargo = self.get_by_id(cargo_id)
        if not cargo:
            return None
        for key, value in kwargs.items():
            setattr(cargo, key, value)
        self.db.commit()
        self.db.refresh(cargo)
        return cargo

    def delete(self, cargo_id: int) -> bool:
        cargo = self.get_by_id(cargo_id)
        if not cargo:
            return False
        try:
            self.db.delete(cargo)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()