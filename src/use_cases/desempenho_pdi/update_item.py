from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository
from src.use_cases.desempenho_pdi.create_item import serializar_item


class UpdatePdiItemRequest(BaseModel):
    nome: Optional[str] = None
    tipo_arquivo: Optional[str] = None
    ordem: Optional[int] = None


class UpdatePdiItemUseCase:
    """Diferente da pasta (`UpdatePdiPastaUseCase`), aqui `tipo_arquivo` pode
    mudar mesmo com envio já feito — só afeta a validação do PRÓXIMO upload,
    não invalida o arquivo que já está salvo."""

    def __init__(self, db: Session):
        self.repository = DesempenhoPdiItemRepository(db)

    def execute(self, item_id: int, request: UpdatePdiItemRequest) -> Optional[dict]:
        dados = request.model_dump(exclude_unset=True)
        item = self.repository.update(item_id, **dados)
        if not item:
            return None
        return serializar_item(item)
