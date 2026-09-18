"""Substituir o rascunho por um .docx editado fora da plataforma (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/use_cases/projeto/reanexar_documento.py`.
Diferente de `editar_texto.py` (reescreve a mesma versão), usa o mecanismo
de "Gerar novo rascunho": cria uma linha nova em `documento_contratual_versao`
com `versao` incrementada, preservando o histórico das versões anteriores.

⚠ A validação de "é um .docx de verdade" e a conversão pra PDF exigem um
arquivo real em disco (LibreOffice) — um diretório temporário existe só
durante esta chamada; o conteúdo final vai pro banco (`docx_conteudo`/
`pdf_conteudo`), nunca um caminho (ver docstring do model).
"""

import os
import tempfile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.utils.exceptions import RegraDeNegocioError
from src.utils.pdf import converter_docx_para_pdf
from src.utils.status_documento_contratual import STATUS_EDICAO_TEXTO


class ReanexarDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)

    def execute(self, documento_id: int, docx_bytes: bytes):
        if not docx_bytes:
            raise RegraDeNegocioError("Envie um arquivo .docx.")

        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            raise RegraDeNegocioError("Documento não encontrado.")
        if documento.status not in STATUS_EDICAO_TEXTO:
            raise RegraDeNegocioError(
                f'Não é possível anexar um novo rascunho com o documento no status "{documento.status}".'
            )

        with tempfile.TemporaryDirectory() as pasta_temp:
            docx_path = os.path.join(pasta_temp, "reanexado.docx")
            with open(docx_path, "wb") as f:
                f.write(docx_bytes)

            try:
                Document(docx_path)
            except PackageNotFoundError:
                raise RegraDeNegocioError("O arquivo enviado não é um .docx válido.")

            pdf_path = converter_docx_para_pdf(docx_path)
            with open(pdf_path, "rb") as f:
                pdf_conteudo = f.read()

        versao = self.versoes.ultima_versao(documento_id) + 1
        versao_criada = self.versoes.create(
            documento_id=documento_id,
            versao=versao,
            status_arquivo="rascunho",
            docx_conteudo=docx_bytes,
            pdf_conteudo=pdf_conteudo,
        )

        self.documentos.update(documento_id, status="em_revisao_interna")
        return versao_criada
