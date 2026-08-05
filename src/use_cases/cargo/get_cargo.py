from sqlalchemy.orm import Session
from src.repositories.cargo_repository import CargoRepository


def serializar_cargo(cargo):
    """Num lugar só — a lista, o get, o create e o update devolvem a mesma
    forma, senão uma permissão nova nasce faltando em metade das telas."""
    return {
        "id": cargo.id,
        "nome": cargo.nome,
        "pode_definir_formulario": cargo.pode_definir_formulario,
        "pode_agendar_banca": cargo.pode_agendar_banca,
        "pode_gerenciar_cargos": cargo.pode_gerenciar_cargos,
        "pode_gerenciar_membros": cargo.pode_gerenciar_membros,
        "pode_gerenciar_nucleo": cargo.pode_gerenciar_nucleo,
        "pode_gerenciar_desempenho": cargo.pode_gerenciar_desempenho,
        "pode_definir_formulario_desempenho": cargo.pode_definir_formulario_desempenho,
    }


class GetCargoUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self, cargo_id: int):
        cargo = self.repository.get_by_id(cargo_id)
        if not cargo:
            return None
        return serializar_cargo(cargo)


class ListCargosUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self):
        return [serializar_cargo(c) for c in self.repository.get_all()]
