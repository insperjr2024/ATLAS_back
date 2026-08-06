"""Troca de candidatura de banca (§8) — pedido aberto: quem não pode
comparecer abre o pedido, qualquer consultor elegível confirma."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.solicitacao_troca.cancelar_solicitacao_troca import CancelarSolicitacaoTrocaUseCase
from src.use_cases.solicitacao_troca.confirmar_solicitacao_troca import ConfirmarSolicitacaoTrocaUseCase
from src.use_cases.solicitacao_troca.create_solicitacao_troca import (
    CreateSolicitacaoTrocaRequest,
    CreateSolicitacaoTrocaUseCase,
)
from src.use_cases.solicitacao_troca.get_solicitacao_troca import ListSolicitacoesTrocaUseCase
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(tags=["solicitações de troca"], dependencies=[Depends(get_current_user)])


@router.post("/solicitacoes-troca")
def create_solicitacao_troca(
    request: CreateSolicitacaoTrocaRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return CreateSolicitacaoTrocaUseCase(db).execute(request, usuario_id=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/solicitacoes-troca")
def list_solicitacoes_troca(db: Session = Depends(get_db)):
    return ListSolicitacoesTrocaUseCase(db).execute()


@router.post("/solicitacoes-troca/{solicitacao_id}/confirmar")
def confirmar_solicitacao_troca(
    solicitacao_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        return ConfirmarSolicitacaoTrocaUseCase(db).execute(solicitacao_id, usuario_id=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/solicitacoes-troca/{solicitacao_id}/cancelar")
def cancelar_solicitacao_troca(
    solicitacao_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        return CancelarSolicitacaoTrocaUseCase(db).execute(
            solicitacao_id, usuario_id=current_user.id, eh_diretor=current_user.posicao == "diretor"
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
