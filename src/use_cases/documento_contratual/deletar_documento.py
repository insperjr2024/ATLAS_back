"""Apagar um documento jurídico aberto por engano (§ Contratos).

⭐ 2026-09-18 — o sistema antigo só permitia isso enquanto o documento nunca
saiu de "aguardando preenchimento" e não foi confirmado — depois disso vira
um pedido real, que se resolve devolvendo/recusando, não apagando o rastro.
"""

from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.utils.exceptions import RegraDeNegocioError


class DeletarDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)

    def execute(self, documento_id: int) -> None:
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            raise RegraDeNegocioError("Documento não encontrado.")
        if documento.status != "aguardando_preenchimento" or documento.confirmado:
            raise RegraDeNegocioError(
                "Só é possível apagar um documento ainda não confirmado."
            )
        self.documentos.delete(documento_id)
