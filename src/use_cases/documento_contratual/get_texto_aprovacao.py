"""O texto do documento em blocos, pra tela pública de aprovação citar trechos
(§ Contratos).

⭐ 2026-09-20 — a pedido: a pessoa que aprova precisa SELECIONAR o trecho que
quer citar, não digitar de novo. O PDF num `<iframe>` não expõe seleção de
texto pro JavaScript da página (é um documento à parte, renderizado pelo
navegador) — por isso o texto também vai em blocos HTML normais, ao lado do
PDF, só pra esse fim.

Reaproveita `extrair_paragrafos_editaveis` (mesma extração que o Jurídico usa
pra editar o rascunho) — o `ref` não tem uso aqui (ninguém escreve de volta),
só a lista de textos importa.
"""

import os
import tempfile

from sqlalchemy.orm import Session

from src.documentos_contratuais.editar_docx import extrair_paragrafos_editaveis
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.token_aprovacao_contratual_repository import (
    TokenAprovacaoContratualRepository,
)
from src.utils.exceptions import RegraDeNegocioError


class GetTextoAprovacaoPorTokenUseCase:
    def __init__(self, db: Session):
        self.tokens = TokenAprovacaoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)

    def execute(self, token: str) -> list:
        registro = self.tokens.get_by_token(token)
        if not registro:
            raise RegraDeNegocioError("Link inválido.")
        versao = self.versoes.get_by_id(registro.versao_id)
        if not versao or not versao.docx_conteudo:
            raise RegraDeNegocioError("Link inválido.")

        with tempfile.TemporaryDirectory() as pasta_temp:
            docx_path = os.path.join(pasta_temp, "documento.docx")
            with open(docx_path, "wb") as f:
                f.write(versao.docx_conteudo)
            paragrafos = extrair_paragrafos_editaveis(docx_path)

        return [p["texto"] for p in paragrafos]
