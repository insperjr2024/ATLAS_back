from sqlalchemy.orm import Session
from src.repositories.cargo_repository import CargoRepository


def serializar_cargo(cargo):
    """Num lugar só — a lista, o get, o create e o update devolvem a mesma
    forma, senão uma permissão nova nasce faltando em metade das telas."""
    return {
        "id": cargo.id,
        "nome": cargo.nome,
        "pode_criar_projeto": cargo.pode_criar_projeto,
        "pode_editar_equipe": cargo.pode_editar_equipe,
        "pode_gerir_membros": cargo.pode_gerir_membros,
        "pode_marcar_kickoff": cargo.pode_marcar_kickoff,
        "pode_definir_cronograma": cargo.pode_definir_cronograma,
        "pode_criar_tarefa": cargo.pode_criar_tarefa,
        "pode_mover_editar_tarefa": cargo.pode_mover_editar_tarefa,
        "pode_ver_proprios_projetos": cargo.pode_ver_proprios_projetos,
        "pode_ver_monitoramento": cargo.pode_ver_monitoramento,
        "pode_administrar_desempenho": cargo.pode_administrar_desempenho,
        "pode_editar_formularios_desempenho": cargo.pode_editar_formularios_desempenho,
        "pode_ver_nucleo": cargo.pode_ver_nucleo,
        "pode_administrar_configuracoes": cargo.pode_administrar_configuracoes,
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
