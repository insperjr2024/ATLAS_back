from sqlalchemy.orm import Session
from src.repositories.cargo_repository import CargoRepository
from src.use_cases.cargo.get_cargo import serializar_cargo
from pydantic import BaseModel


class CreateCargoRequest(BaseModel):
    nome: str
    pode_criar_projeto: bool = False
    pode_editar_equipe: bool = False
    pode_gerir_membros: bool = False
    pode_marcar_kickoff: bool = False
    pode_definir_cronograma: bool = False
    pode_criar_tarefa: bool = False
    pode_mover_editar_tarefa: bool = False
    pode_ver_proprios_projetos: bool = False
    pode_ver_monitoramento: bool = False
    pode_administrar_desempenho: bool = False
    pode_editar_formularios_desempenho: bool = False
    pode_ver_nucleo: bool = False
    pode_administrar_configuracoes: bool = False


class CreateCargoUseCase:
    def __init__(self, db: Session):
        self.repository = CargoRepository(db)

    def execute(self, request: CreateCargoRequest):
        cargo = self.repository.create(**request.model_dump())
        return serializar_cargo(cargo)
