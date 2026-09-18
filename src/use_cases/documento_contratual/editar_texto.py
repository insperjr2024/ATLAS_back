"""Ler e editar o texto do rascunho gerado, parágrafo por parágrafo (§ Contratos).

⭐ 2026-09-16 — porta de `PATCH /contratos/{id}/documento/texto` (uso de
`editar_docx.py`). Edita a ÚLTIMA versão IN PLACE (mesma linha, `docx_
conteudo`/`pdf_conteudo` atualizados) — não cria uma versão nova (diferente
de gerar/reanexar).

⚠ 2026-09-18 — `editar_docx.py` só sabe editar um ARQUIVO em disco (é
`python-docx`, não dá pra editar bytes em memória direto). O conteúdo em si
mora no banco (ver docstring do model): grava os bytes atuais num arquivo
temporário, edita ali, lê de volta, e o diretório desaparece com o `with` —
nada sobrevive em disco além desta chamada.
"""

import os
import tempfile
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
        with tempfile.TemporaryDirectory() as pasta_temp:
            docx_path = os.path.join(pasta_temp, "rascunho.docx")
            with open(docx_path, "wb") as f:
                f.write(versao.docx_conteudo)
            return extrair_paragrafos_editaveis(docx_path)


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

        with tempfile.TemporaryDirectory() as pasta_temp:
            docx_path = os.path.join(pasta_temp, "rascunho.docx")
            with open(docx_path, "wb") as f:
                f.write(versao.docx_conteudo)

            alterados = aplicar_edicoes(docx_path, edicoes)
            pdf_path = converter_docx_para_pdf(docx_path)

            with open(docx_path, "rb") as f:
                docx_conteudo = f.read()
            with open(pdf_path, "rb") as f:
                pdf_conteudo = f.read()

        self.versoes.update(versao.id, docx_conteudo=docx_conteudo, pdf_conteudo=pdf_conteudo)
        return {"alterados": alterados}


def _documento_e_ultima_versao(documentos, versoes, documento_id: int):
    documento = documentos.get_by_id(documento_id)
    if not documento:
        raise RegraDeNegocioError("Documento não encontrado.")
    versao = versoes.ultima_versao_obj(documento_id)
    if not versao:
        raise RegraDeNegocioError("Nenhum rascunho gerado ainda para este documento.")
    return documento, versao
