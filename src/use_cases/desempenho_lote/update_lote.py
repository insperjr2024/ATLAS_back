from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.use_cases.desempenho_lote.get_lote import serializar_lote


class UpdateDesempenhoLoteRequest(BaseModel):
    nome: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    projeto_ids: Optional[List[int]] = None


class UpdateDesempenhoLoteUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)

    def execute(self, lote_id: int, request: UpdateDesempenhoLoteRequest) -> Optional[dict]:
        dados = request.dict(exclude_unset=True, exclude={"projeto_ids"})
        lote = self.lote_repo.update(lote_id, **dados) if dados else self.lote_repo.get_by_id(lote_id)
        if not lote:
            return None

        if request.projeto_ids is not None:
            for vinculo in self.lote_projeto_repo.filter_by(lote_id=lote_id):
                self.lote_projeto_repo.delete(vinculo.id)
            if request.projeto_ids:
                self.lote_projeto_repo.bulk_create(
                    [{"lote_id": lote_id, "projeto_id": pid} for pid in request.projeto_ids]
                )

        return serializar_lote(lote, self.lote_projeto_repo.get_projeto_ids(lote_id))
