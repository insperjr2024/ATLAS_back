from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_lote_finalizado_repository import DesempenhoLoteFinalizadoRepository


class FinalizarDesempenhoRequest(BaseModel):
    lote_id: int


class FinalizarDesempenhoUseCase:
    """Regra 2.4: idempotente por design — o `UniqueConstraint(lote_id,
    usuario_id)` garante que chamar de novo não duplica; a checagem prévia
    evita bater na constraint à toa."""

    def __init__(self, db: Session):
        self.repository = DesempenhoLoteFinalizadoRepository(db)

    def execute(self, usuario_id: int, lote_id: int) -> dict:
        ja_existe = self.repository.first_by(lote_id=lote_id, usuario_id=usuario_id)
        if not ja_existe:
            self.repository.create(lote_id=lote_id, usuario_id=usuario_id)
        return {"lote_id": lote_id, "usuario_id": usuario_id, "finalizado": True}
