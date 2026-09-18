"""Ler e editar o texto do rascunho gerado, parágrafo por parágrafo (§ Contratos).

⭐ 2026-09-18 — porta de `PATCH /contratos/{id}/documento/texto` (uso de
`editar_docx.py`). Edita o `.docx` da ÚLTIMA versão IN PLACE — não cria uma
versão nova (diferente de gerar/reanexar) — e reconverte pra PDF, senão a
tela de aprovação mostraria um PDF desatualizado.
"""

from typing import Dict, List

from sqlalchemy.orm import Session

from src.documentos_contratuais.editar_docx import aplicar_edicoes, extrair_paragrafos_editaveis
from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.utils.exceptions import RegraDeNegocioError
from src.utils.pdf import converter_docx_para_pdf
from src.utils.status_documento_contratual import STATUS_EDICAO_TEXTO


class GetParagrafosEditaveisUseCase:
    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)

    def execute(self, documento_id: int) -> List[dict]:
        documento, versao = _documento_e_ultima_versao(self.documentos, self.versoes, documento_id)
        if documento.status not in STATUS_EDICAO_TEXTO:
            raise RegraDeNegocioError(
                f'Não é possível editar o texto com o documento no status "{documento.status}".'
            )
        return extrair_paragrafos_editaveis(versao.docx_path)


class EditarTextoDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)

    def execute(self, documento_id: int, edicoes: Dict[int, str]) -> dict:
        documento, versao = _documento_e_ultima_versao(self.documentos, self.versoes, documento_id)
        if documento.status not in STATUS_EDICAO_TEXTO:
            raise RegraDeNegocioError(
                f'Não é possível editar o texto com o documento no status "{documento.status}".'
            )
        if not edicoes:
            raise RegraDeNegocioError("Nenhuma edição enviada.")

        alterados = aplicar_edicoes(versao.docx_path, edicoes)
        converter_docx_para_pdf(versao.docx_path)
        return {"alterados": alterados}


def _documento_e_ultima_versao(documentos, versoes, documento_id: int):
    documento = documentos.get_by_id(documento_id)
    if not documento:
        raise RegraDeNegocioError("Documento não encontrado.")
    versao = versoes.ultima_versao_obj(documento_id)
    if not versao:
        raise RegraDeNegocioError("Nenhum rascunho gerado ainda para este documento.")
    return documento, versao
