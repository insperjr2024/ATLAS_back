"""Aprovar por dentro o rascunho gerado, antes de liberar o envio ao cliente
(§ Contratos).

⭐ 2026-09-21 — a pedido: até aqui "gerar o rascunho" e "mandar pro cliente"
eram a mesma permissão (Jurídico/diretoria) — na prática ela quer duas
pessoas diferentes em cada ponta: o Jurídico (Valentina) valida o texto por
dentro, e quem manda pro cliente pode ser o vendedor do projeto (Contrato de
Prestação) ou ela e os coordenadores (TEP). Esta é a aprovação — o gate de
quem pode MANDAR depois dela mora no router (`_pode_enviar_ao_cliente`).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.notificar_documento_contratual import documento_aprovado_internamente
from src.utils.status_documento_contratual import STATUS_APROVACAO_INTERNA_PERMITIDA


class AprovarInternamenteDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.documentos = DocumentoContratualRepository(db)

    def execute(self, documento_id: int, aprovado_por: int):
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            raise RegraDeNegocioError("Documento não encontrado.")
        if documento.status not in STATUS_APROVACAO_INTERNA_PERMITIDA:
            raise RegraDeNegocioError(
                f'Não é possível aprovar internamente com o documento no status "{documento.status}".'
            )

        # ⭐ 2026-09-22 — a pedido: registro de auditoria (quem aprovou,
        # quando) — mostrado na tela, não só uma notificação que some do
        # sino depois de lida.
        aprovado = self.documentos.update(
            documento_id,
            status="aprovado_internamente",
            aprovado_internamente_por=aprovado_por,
            aprovado_internamente_em=datetime.now(),
        )
        documento_aprovado_internamente(self.db, aprovado)
        return aprovado
