"""Declaração de interesse do consultor em entrar num projeto."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.solicitacao_projeto.solicitacao_projeto import (
    CriarSolicitacaoRequest,
    ResponderSolicitacaoRequest,
    SolicitacaoProjetoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

# Todo mundo logado: ver vaga e pedir é de qualquer um. Quem RESPONDE é
# checado dentro do use case — tem que ser o coordenador daquele projeto,
# e isso não cabe numa guarda de cargo.
router = APIRouter(tags=["solicitacoes-projeto"], dependencies=[Depends(get_current_user)])


@router.get("/projetos-com-vaga")
def projetos_com_vaga(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Os projetos abertos, cada um já dizendo se ESTA pessoa pode pedir.

    O `impedimento` vem preenchido em vez de o projeto sumir da lista: some
    sem explicação é o que gera "por que não aparece o projeto X?".
    """
    try:
        return SolicitacaoProjetoUseCase(db).listar_vagas(current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/solicitacoes-projeto")
def criar_solicitacao(
    request: CriarSolicitacaoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return SolicitacaoProjetoUseCase(db).criar(current_user.id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/solicitacoes-projeto/minhas")
def minhas_solicitacoes(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return SolicitacaoProjetoUseCase(db).listar_meus(current_user.id)


@router.get("/solicitacoes-projeto/recebidas")
def solicitacoes_recebidas(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Os pedidos que o usuário logado pode responder.

    Coordenador vê os projetos dele; gerência e diretoria veem os que
    enxergam. Sem guarda de cargo aqui: quem não tem nada recebe lista vazia.
    """
    return SolicitacaoProjetoUseCase(db).listar_do_coordenador(current_user)


@router.patch("/solicitacoes-projeto/{solicitacao_id}")
def responder_solicitacao(
    solicitacao_id: int,
    request: ResponderSolicitacaoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aceitar já inclui a pessoa na equipe como consultor.

    Respondem: o coordenador do projeto, a gerência da frente e a diretoria.
    Para o coordenador é poder novo e estreito — ele não ganha
    `pode_editar_equipe`, só aceita quem pediu para entrar no projeto dele.
    """
    try:
        return SolicitacaoProjetoUseCase(db).responder(solicitacao_id, current_user, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/solicitacoes-projeto/{solicitacao_id}", status_code=204)
def cancelar_solicitacao(
    solicitacao_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """O próprio solicitante desiste, enquanto ainda está pendente."""
    try:
        SolicitacaoProjetoUseCase(db).cancelar(solicitacao_id, current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
