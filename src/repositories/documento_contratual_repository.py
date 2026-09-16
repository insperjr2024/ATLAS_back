from typing import List, Optional

from src.models.documento_contratual_model import DocumentoContratualModel
from src.repositories.base_repository import BaseRepository


class DocumentoContratualRepository(BaseRepository[DocumentoContratualModel]):
    model = DocumentoContratualModel

    def list_by_projeto(self, projeto_id: int) -> List[DocumentoContratualModel]:
        return (
            self.db.query(DocumentoContratualModel)
            .filter(DocumentoContratualModel.projeto_id == projeto_id)
            .order_by(DocumentoContratualModel.criado_em)
            .all()
        )

    def get_by_projeto_e_tipo(self, projeto_id: int, tipo: str) -> Optional[DocumentoContratualModel]:
        return self.first_by(projeto_id=projeto_id, tipo=tipo)
