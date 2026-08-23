from sqlalchemy.orm import Session
from src.repositories.frente_repository import FrenteRepository


def serializar_frente(frente):
    return {
        "id": frente.id,
        "nome": frente.nome,
        "ativa": frente.ativa,
        "piso_banca": frente.piso_banca,
        # Qual dos calendários da frente vale para quem não escolheu. Nulo na
        # frente que tem um calendário só, que é o caso de três das quatro.
        "calendario_padrao": frente.calendario_padrao,
    }


class GetFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = FrenteRepository(db)

    def execute(self, frente_id: int):
        frente = self.repository.get_by_id(frente_id)
        if not frente:
            return None
        return serializar_frente(frente)


class ListFrentesUseCase:
    def __init__(self, db: Session):
        self.repository = FrenteRepository(db)

    def execute(self, apenas_ativas: bool = False):
        frentes = self.repository.get_all()
        if apenas_ativas:
            frentes = [f for f in frentes if f.ativa]
        return [serializar_frente(f) for f in frentes]
