"""§ Contratos — a tela pública de aprovação, sem login.

⭐ 2026-09-18 — quem recebe o link de aprovação (`ExportarAprovacaoDocumentoContratualUseCase`)
não tem conta no ATLAS: é o representante do cliente. Mesma família de rota
pública que `auth.router_publico` (login, esqueci-senha) — um `APIRouter`
sem `Depends(get_current_user)`, o TOKEN de uso único é a única credencial.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.token_aprovacao_contratual_repository import (
    TokenAprovacaoContratualRepository,
)
from src.use_cases.documento_contratual.get_aprovacao_por_token import (
    GetAprovacaoPorTokenUseCase,
)
from src.use_cases.documento_contratual.get_texto_aprovacao import (
    GetTextoAprovacaoPorTokenUseCase,
)
from src.use_cases.documento_contratual.responder_aprovacao import (
    ResponderAprovacaoRequest,
    ResponderAprovacaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

router_publico = APIRouter(tags=["aprovação contratual"])


@router_publico.get("/aprovacao/{token}")
def get_aprovacao(token: str, db: Session = Depends(get_db)):
    try:
        return GetAprovacaoPorTokenUseCase(db).execute(token)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router_publico.get("/aprovacao/{token}/arquivo")
def download_arquivo_aprovacao(token: str, db: Session = Depends(get_db)):
    """O PDF exato que este link aponta — sempre a VERSÃO travada no token no
    momento da exportação, não a última do documento (que pode já ter mudado
    se o Jurídico gerou de novo sob um link diferente)."""
    registro = TokenAprovacaoContratualRepository(db).get_by_token(token)
    if not registro:
        raise HTTPException(status_code=404, detail="Link inválido.")
    versao = DocumentoContratualVersaoRepository(db).get_by_id(registro.versao_id)
    if not versao or not versao.pdf_conteudo:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return Response(
        content=versao.pdf_conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="documento.pdf"'},
    )


@router_publico.get("/aprovacao/{token}/texto")
def get_texto_aprovacao(token: str, db: Session = Depends(get_db)):
    try:
        return {"paragrafos": GetTextoAprovacaoPorTokenUseCase(db).execute(token)}
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router_publico.post("/aprovacao/{token}/responder")
def responder_aprovacao(
    token: str, request: ResponderAprovacaoRequest, db: Session = Depends(get_db)
):
    try:
        return ResponderAprovacaoUseCase(db).execute(token, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))
