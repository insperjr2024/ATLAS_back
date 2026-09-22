"""Resposta do cliente na tela pública de aprovação (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/use_cases/aprovacao/responder.py`.
Endpoint sem login, então os limites de tamanho/quantidade dos trechos citados
são validados AQUI, antes de qualquer escrita.

⚠ Pedir alteração NÃO edita o documento sozinho — só sinaliza pro Jurídico
ajustar e gerar de novo (ver `analisar_solicitacao.py`).
"""

from typing import List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.solicitacao_alteracao_contratual_repository import (
    SolicitacaoAlteracaoContratualRepository,
)
from src.repositories.token_aprovacao_contratual_repository import (
    TokenAprovacaoContratualRepository,
)
from src.utils.exceptions import RegraDeNegocioError
from src.utils.notificar_documento_contratual import cliente_respondeu

MAXIMO_TRECHOS = 20
TAMANHO_MAXIMO_TRECHO = 1000


class ResponderAprovacaoRequest(BaseModel):
    acao: Literal["aprovar", "alteracao"]
    texto: Optional[str] = None
    trechos: List[str] = []


class ResponderAprovacaoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.tokens = TokenAprovacaoContratualRepository(db)
        self.documentos = DocumentoContratualRepository(db)
        self.solicitacoes = SolicitacaoAlteracaoContratualRepository(db)

    def execute(self, token: str, request: ResponderAprovacaoRequest) -> dict:
        if request.acao == "alteracao" and not (request.texto and request.texto.strip()):
            raise RegraDeNegocioError("Descreva o que precisa ser ajustado.")

        trechos = [t.strip() for t in request.trechos if t.strip()]
        if len(trechos) > MAXIMO_TRECHOS:
            raise RegraDeNegocioError(f"Máximo de {MAXIMO_TRECHOS} trechos citados por pedido.")
        if any(len(t) > TAMANHO_MAXIMO_TRECHO for t in trechos):
            raise RegraDeNegocioError(
                f"Cada trecho citado deve ter no máximo {TAMANHO_MAXIMO_TRECHO} caracteres."
            )

        registro = self.tokens.get_by_token(token)
        if not registro:
            raise RegraDeNegocioError("Link inválido.")
        if registro.usado:
            raise RegraDeNegocioError("Este link já foi usado.")

        documento = self.documentos.get_by_id(registro.documento_id)
        if not documento:
            raise RegraDeNegocioError("Link inválido.")

        if request.acao == "aprovar":
            self.documentos.update(documento.id, status="aprovado_pelo_cliente")
            cliente_respondeu(self.db, documento, aprovado=True)
        else:
            self.documentos.update(documento.id, status="alteracao_solicitada")
            self.solicitacoes.create(
                documento_id=documento.id,
                versao_id=registro.versao_id,
                texto=request.texto.strip(),
                trechos=trechos,
            )
            cliente_respondeu(self.db, documento, aprovado=False, motivo=request.texto.strip())

        self.tokens.marcar_usado(registro)
        return {"ok": True}
