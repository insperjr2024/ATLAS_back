"""Apagar um documento jurídico aberto por engano (§ Contratos).

⭐ 2026-09-18 — o sistema antigo só permitia isso enquanto o documento nunca
saiu de "aguardando preenchimento" e não foi confirmado — depois disso vira
um pedido real, que se resolve devolvendo/recusando, não apagando o rastro.
"""

import logging

from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.use_cases.arquivo_contratos.arquivar import marcar_documento_deletado
from src.utils.exceptions import RegraDeNegocioError



logger = logging.getLogger(__name__)

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
        # O arquivo de contratos guarda o PDF com "[DELETADO] " no nome; se
        # isso falhar, não pode travar a exclusão em si.
        try:
            marcar_documento_deletado(self.db, documento_id)
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao marcar o documento como deletado no arquivo de contratos")
        self.documentos.delete(documento_id)
