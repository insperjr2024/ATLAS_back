from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.documento_contratual_model import DocumentoContratualModel
from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)


def serializar_documento_contratual(
    documento: DocumentoContratualModel, ultima_versao: Optional[int] = None
) -> dict:
    return {
        "id": documento.id,
        "projeto_id": documento.projeto_id,
        "tipo": documento.tipo,
        "status": documento.status,
        "dados": documento.dados,
        "confirmado": documento.confirmado,
        "gestao_id": documento.gestao_id,
        "criado_em": documento.criado_em,
        "atualizado_em": documento.atualizado_em,
        "ultima_versao": ultima_versao,
    }


class GetDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)

    def execute(self, documento_id: int) -> Optional[dict]:
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            return None
        ultima_versao = self.versoes.ultima_versao(documento_id)
        return serializar_documento_contratual(documento, ultima_versao or None)


class ListDocumentosContratuaisPorProjetoUseCase:
    """Todos os documentos jurídicos de um projeto — a aba Contratos dele."""

    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)

    def execute(self, projeto_id: int) -> List[dict]:
        documentos = self.documentos.list_by_projeto(projeto_id)
        return [
            serializar_documento_contratual(d, self.versoes.ultima_versao(d.id) or None)
            for d in documentos
        ]
