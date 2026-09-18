"""§ Contratos — a tela pública de aprovação, sem login.

⭐ 2026-09-18 — quem recebe o link de aprovação (`ExportarAprovacaoDocumentoContratualUseCase`)
não tem conta no ATLAS: é o representante do cliente. Mesma família de rota
pública que `auth.router_publico` (login, esqueci-senha) — um `APIRouter`
sem `Depends(get_current_user)`, o TOKEN de uso único é a única credencial.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.use_cases.documento_contratual.get_aprovacao_por_token import (
    GetAprovacaoPorTokenUseCase,
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


@router_publico.post("/aprovacao/{token}/responder")
def responder_aprovacao(
    token: str, request: ResponderAprovacaoRequest, db: Session = Depends(get_db)
):
    try:
        return ResponderAprovacaoUseCase(db).execute(token, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))
