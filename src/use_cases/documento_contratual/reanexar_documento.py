"""Substituir o rascunho por um .docx editado fora da plataforma (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/use_cases/projeto/reanexar_documento.py`.
Diferente de `editar_texto.py` (reescreve o mesmo arquivo, mesma versão),
usa o mecanismo de "Gerar novo rascunho": cria uma linha nova em
`documento_contratual_versao` com `versao` incrementada, preservando o
histórico das versões anteriores.
"""

import os

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

GERADOS_DIR = os.path.join(os.getcwd(), "gerados", "documentos_contratuais")


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

        versao = self.versoes.ultima_versao(documento_id) + 1
        pasta_projeto = os.path.join(GERADOS_DIR, str(documento.projeto_id))
        os.makedirs(pasta_projeto, exist_ok=True)
        nome_base = f"{documento.tipo}_v{versao}"
        docx_path = os.path.join(pasta_projeto, f"{nome_base}.docx")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)

        try:
            Document(docx_path)
        except PackageNotFoundError:
            os.remove(docx_path)
            raise RegraDeNegocioError("O arquivo enviado não é um .docx válido.")

        pdf_path = converter_docx_para_pdf(docx_path)

        versao_criada = self.versoes.create(
            documento_id=documento_id,
            versao=versao,
            status_arquivo="rascunho",
            docx_path=docx_path,
            pdf_path=pdf_path,
        )

        self.documentos.update(documento_id, status="em_revisao_interna")
        return versao_criada
