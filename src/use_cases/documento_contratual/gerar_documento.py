"""Gerar um novo rascunho (.docx + .pdf) de um documento jurídico (§ Contratos).

⭐ 2026-09-16 — porta de `contratos-backend/src/use_cases/projeto/gerar_documento.py`,
trocando `ContratoRepository`/`DocumentoRepository`/`ConfiguracaoRepository`
(Contratos) por `DocumentoContratualRepository`/`DocumentoContratualVersaoRepository`/
`IdentidadeInstitucionalRepository` (ATLAS).

⚠ Cada chamada cria uma VERSÃO nova (`versao + 1`), nunca sobrescreve a
anterior — o histórico de rascunhos de um documento fica todo em
`documento_contratual_versao`. Gerar de novo também devolve o documento pro
começo do fluxo interno (`em_revisao_interna`), mesmo que ele já estivesse
com alteração solicitada pelo cliente.
"""

import os

from sqlalchemy.orm import Session

from src.documentos_contratuais.render_template import TEMPLATE_POR_TIPO, renderizar
from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.identidade_institucional_repository import IdentidadeInstitucionalRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.identidade_institucional import identidade_de_configuracao
from src.utils.pdf import converter_docx_para_pdf
from src.utils.status_documento_contratual import STATUS_GERACAO_PERMITIDA

GERADOS_DIR = os.path.join(os.getcwd(), "gerados", "documentos_contratuais")


class GerarDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)
        self.identidade = IdentidadeInstitucionalRepository(db)

    def execute(self, documento_id: int):
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            raise RegraDeNegocioError("Documento não encontrado.")
        if documento.status not in STATUS_GERACAO_PERMITIDA:
            raise RegraDeNegocioError(
                f'Não é possível gerar um novo rascunho com o documento no status "{documento.status}".'
            )
        if documento.tipo not in TEMPLATE_POR_TIPO:
            raise RegraDeNegocioError(f'Não há template para documentos do tipo "{documento.tipo}".')
        if not documento.dados:
            raise RegraDeNegocioError(f'Dados de "{documento.tipo}" ainda não preenchidos.')

        identidade = identidade_de_configuracao(self.identidade.get())
        doc = renderizar(documento.tipo, documento.dados, identidade)

        versao = self.versoes.ultima_versao(documento_id) + 1
        pasta_projeto = os.path.join(GERADOS_DIR, str(documento.projeto_id))
        os.makedirs(pasta_projeto, exist_ok=True)
        nome_base = f"{documento.tipo}_v{versao}"
        docx_path = os.path.join(pasta_projeto, f"{nome_base}.docx")
        doc.save(docx_path)

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
