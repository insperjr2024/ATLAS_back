"""Confirmar que os dados de um documento jurídico estão certos (§ Contratos).

⭐ 2026-09-16 — porta de `POST /contratos/{id}/confirmar`. Quem preencheu
confirma e manda pro Jurídico — até aqui dava pra editar ou desistir à
vontade; depois desta chamada, a edição vira função de quem tem
`pode_editar_documento_juridico` (ver `atualizar_dados.py`).
"""

from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.utils.exceptions import RegraDeNegocioError


class ConfirmarPreenchimentoDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)

    def execute(self, documento_id: int):
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            raise RegraDeNegocioError("Documento não encontrado.")
        if documento.status != "aguardando_preenchimento":
            raise RegraDeNegocioError(
                'Só é possível confirmar um documento "aguardando preenchimento".'
            )
        if documento.confirmado:
            raise RegraDeNegocioError("Este documento já foi confirmado.")

        return self.documentos.update(documento_id, confirmado=True)
