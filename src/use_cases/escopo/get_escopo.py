from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.escopo_repository import EscopoRepository


def serializar_escopo(escopo):
    return {
        "id": escopo.id,
        "nome": escopo.nome,
        "frente_id": escopo.frente_id,
        "ativo": escopo.ativo,
    }


class GetEscopoUseCase:
    def __init__(self, db: Session):
        self.repository = EscopoRepository(db)

    def execute(self, escopo_id: int):
        escopo = self.repository.get_by_id(escopo_id)
        if not escopo:
            return None
        return serializar_escopo(escopo)


class ListEscoposUseCase:
    def __init__(self, db: Session):
        self.repository = EscopoRepository(db)

    def execute(self, frente_id: Optional[int] = None, apenas_ativos: bool = False):
        """A tela de criar projeto filtra por frente (§6.3): só aparecem os
        escopos das frentes marcadas."""
        escopos = (
            self.repository.get_by_frente(frente_id)
            if frente_id is not None
            else self.repository.get_all()
        )
        if apenas_ativos:
            escopos = [e for e in escopos if e.ativo]
        return [serializar_escopo(e) for e in escopos]