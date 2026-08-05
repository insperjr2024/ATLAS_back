from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.utils.desempenho_lote import esta_aberto


def serializar_lote(lote, projeto_ids: list[int]) -> dict:
    return {
        "id": lote.id,
        "nome": lote.nome,
        "tipo": lote.tipo,
        "data_inicio": lote.data_inicio,
        "data_fim": lote.data_fim,
        "override_manual": lote.override_manual,
        "projeto_ids": projeto_ids,
        "aberto": esta_aberto(lote.override_manual, lote.data_inicio, lote.data_fim),
    }


class GetDesempenhoLoteUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)

    def execute(self, lote_id: int) -> Optional[dict]:
        lote = self.lote_repo.get_by_id(lote_id)
        if not lote:
            return None
        return serializar_lote(lote, self.lote_projeto_repo.get_projeto_ids(lote_id))


class ListDesempenhoLotesUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)

    def execute(self, abertos: bool = True) -> list[dict]:
        lotes = self.lote_repo.get_abertos_agora() if abertos else self.lote_repo.get_all()
        return [
            serializar_lote(lote, self.lote_projeto_repo.get_projeto_ids(lote.id))
            for lote in lotes
        ]
