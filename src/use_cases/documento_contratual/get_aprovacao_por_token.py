"""Ler o que a tela pública de aprovação mostra (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/use_cases/aprovacao/get_by_token.py`.
Endpoint sem login: a resposta carrega só o que a pessoa que recebeu o link
precisa ver, nada de dado interno do projeto.
"""

from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.token_aprovacao_contratual_repository import (
    TokenAprovacaoContratualRepository,
)
from src.utils.exceptions import RegraDeNegocioError


class GetAprovacaoPorTokenUseCase:
    def __init__(self, db: Session):
        self.tokens = TokenAprovacaoContratualRepository(db)
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)

    def execute(self, token: str) -> dict:
        registro = self.tokens.get_by_token(token)
        if not registro:
            raise RegraDeNegocioError("Link inválido.")
        documento = self.documentos.get_by_id(registro.documento_id)
        versao = self.versoes.get_by_id(registro.versao_id)
        if not documento or not versao:
            raise RegraDeNegocioError("Link inválido.")

        return {
            "usado": registro.usado,
            "nome_projeto": documento.projeto.nome,
            "tipo_documento": documento.tipo,
            "status": documento.status,
        }
