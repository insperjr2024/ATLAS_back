from datetime import datetime
from typing import List, Optional

from src.models.documento_contratual_versao_model import DocumentoContratualVersaoModel
from src.repositories.base_repository import BaseRepository


class DocumentoContratualVersaoRepository(BaseRepository[DocumentoContratualVersaoModel]):
    model = DocumentoContratualVersaoModel

    def list_by_documento(self, documento_id: int) -> List[DocumentoContratualVersaoModel]:
        """Versões de um documento, da mais recente pra mais antiga."""
        return (
            self.db.query(DocumentoContratualVersaoModel)
            .filter(DocumentoContratualVersaoModel.documento_id == documento_id)
            .order_by(DocumentoContratualVersaoModel.versao.desc())
            .all()
        )

    def ultima_versao(self, documento_id: int) -> int:
        versoes = self.list_by_documento(documento_id)
        return versoes[0].versao if versoes else 0

    def ultima_versao_obj(self, documento_id: int) -> Optional[DocumentoContratualVersaoModel]:
        """A linha da versão mais recente (não só o número) — quem precisa
        do arquivo em si (exportar pro cliente, marcar como assinado) usa
        esta, não `ultima_versao`."""
        versoes = self.list_by_documento(documento_id)
        return versoes[0] if versoes else None

    def marcar_final(self, versao: DocumentoContratualVersaoModel, gestao_id: int) -> DocumentoContratualVersaoModel:
        versao.status_arquivo = "final_assinado"
        versao.gestao_id = gestao_id
        versao.arquivado_em = datetime.now()
        self.db.commit()
        self.db.refresh(versao)
        return versao
