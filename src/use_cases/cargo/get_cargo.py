from sqlalchemy.orm import Session
from src.repositories.cargo_repository import CargoRepository


class GetCargoUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self, cargo_id: int):
        cargo = self.repository.get_by_id(cargo_id)
        if not cargo:
            return None
        return {
            "id": cargo.id,
            "nome": cargo.nome,
            "categoria_banca": cargo.categoria_banca,
            "pode_definir_formulario": cargo.pode_definir_formulario,
            "pode_agendar_banca": cargo.pode_agendar_banca,
            "pode_gerenciar_cargos": cargo.pode_gerenciar_cargos
        }


class ListCargosUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self):
        cargos = self.repository.get_all()
        return [
            {
                "id": c.id,
                "nome": c.nome,
                "categoria_banca": c.categoria_banca,
                "pode_definir_formulario": c.pode_definir_formulario,
                "pode_agendar_banca": c.pode_agendar_banca,
                "pode_gerenciar_cargos": c.pode_gerenciar_cargos
            }
            for c in cargos
        ]