"""Declaração de interesse do consultor em entrar num projeto."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.solicitacao_projeto.solicitacao_projeto import (
    AlocarDiretoRequest,
    CriarSolicitacaoRequest,
    ResponderSolicitacaoRequest,
    SolicitacaoProjetoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

# Todo mundo logado: ver a página é de qualquer um, e cada rota devolve o que
# aquela pessoa pode ver. Quem RESPONDE e quem ALOCA é checado dentro do use
# case, porque depende do projeto (a frente do gerente), e isso não cabe numa
# guarda de posição no router.
router = APIRouter(tags=["solicitacoes-projeto"], dependencies=[Depends(get_current_user)])


@router.get("/projetos-com-vaga")
def projetos_com_vaga(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Os projetos abertos, cada um já dizendo se ESTA pessoa pode pedir.

    O `impedimento` vem preenchido em vez de o projeto sumir da lista: some
    sem explicação é o que gera "por que não aparece o projeto X?".

    Traz também `pode_solicitar` e `pode_responder`, que decidem quais abas a
    página monta.
    """
    try:
        return SolicitacaoProjetoUseCase(db).listar_vagas(current_user)
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
    """Os pedidos que o usuário logado pode responder — gerência e diretoria.

    O gerente fica na frente dele; a diretoria vê tudo. Sem guarda de posição
    aqui: quem não monta equipe recebe lista vazia, coordenador incluído.
    """
    return SolicitacaoProjetoUseCase(db).listar_para_decisao(current_user)


@router.get("/solicitacoes-projeto/meus-projetos")
def projetos_que_coordeno(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """A visão de LEITURA do coordenador: o time de cada projeto dele e quem
    pediu para entrar. Nenhuma ação sai daqui — a decisão é da gestão."""
    return SolicitacaoProjetoUseCase(db).listar_projetos_coordenados(current_user)


@router.get("/solicitacoes-projeto/candidatos/{projeto_id}")
def candidatos_para_alocar(
    projeto_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Quem pode ser alocado NESTE projeto, do menos carregado ao mais.

    Traz carga em número, a situação da escala da diretoria e as frentes de
    cada um — é com isso que o painel agrupa, filtra e ordena.
    """
    try:
        return SolicitacaoProjetoUseCase(db).listar_candidatos(current_user, projeto_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/solicitacoes-projeto/alocar")
def alocar_direto(
    request: AlocarDiretoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """A gestão coloca alguém no projeto sem pedido prévio.

    Mesmo efeito de editar a equipe pela página do projeto — existe para não
    obrigar a sair da tela de solicitações no meio da decisão.
    """
    try:
        return SolicitacaoProjetoUseCase(db).alocar_direto(current_user, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/solicitacoes-projeto/{solicitacao_id}")
def responder_solicitacao(
    solicitacao_id: int,
    request: ResponderSolicitacaoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aceitar já inclui a pessoa na equipe como consultor.

    Respondem a gerência da frente e a diretoria. O coordenador do projeto
    não decide — ele acompanha pela rota `meus-projetos`.
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
