from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.cargo_repository import CargoRepository
from src.use_cases.cargo.get_cargo import serializar_cargo


class UpdateCargoRequest(BaseModel):
    nome: Optional[str] = None
    pode_criar_projeto: Optional[bool] = None
    pode_editar_equipe: Optional[bool] = None
    pode_gerir_membros: Optional[bool] = None
    pode_marcar_kickoff: Optional[bool] = None
    pode_definir_cronograma: Optional[bool] = None
    pode_aprovar_reajuste: Optional[bool] = None
    pode_criar_tarefa: Optional[bool] = None
    pode_mover_editar_tarefa: Optional[bool] = None
    pode_ver_proprios_projetos: Optional[bool] = None
    pode_ver_monitoramento: Optional[bool] = None
    pode_administrar_desempenho: Optional[bool] = None
    pode_editar_formularios_desempenho: Optional[bool] = None
    pode_ver_nucleo: Optional[bool] = None
    pode_administrar_configuracoes: Optional[bool] = None


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
