"""Sabatina: o processo eleitoral. Ver `models/sabatina_model.py`.

Montar, abrir, fechar, excluir, ver apuração, pendências e gráficos: quem
tem a caixa `pode_acessar_configuracoes_sabatina` (nasce marcada pra
diretoria). Votar e ver a própria cédula: qualquer pessoa logada que esteja
entre os eleitores congelados na abertura.

Voto anônimo: nenhuma rota devolve quem votou em quem, nem pra diretoria.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import require_pode_acessar_configuracoes_sabatina
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.sabatina.eleicoes import (
    AbrirEleicaoUseCase,
    CreateEleicaoUseCase,
    DeleteEleicaoUseCase,
    EleicaoRequest,
    FecharEleicaoUseCase,
    GetEleicaoUseCase,
    GetGraficosEleicaoUseCase,
    ListEleicoesUseCase,
    UpdateEleicaoUseCase,
)
from src.use_cases.sabatina.pesos import GetPesosUseCase, UpdatePesosRequest, UpdatePesosUseCase
from src.use_cases.sabatina.votar import MinhasEleicoesUseCase, VotarUseCase, VotoRequest
from src.utils.erro_http import erro_de_regra
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(prefix="/sabatina", tags=["sabatina"], dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------- todo mundo

@router.get("/minhas")
def minhas(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return MinhasEleicoesUseCase(db).execute(current_user.id)


@router.post("/eleicoes/{eleicao_id}/votar", status_code=201)
def votar(
    eleicao_id: int,
    request: VotoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return VotarUseCase(db).execute(eleicao_id, request, current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


# ---------------------------------------------------------------- configuração

@router.get("/pesos")
def pesos(_=Depends(require_pode_acessar_configuracoes_sabatina), db: Session = Depends(get_db)):
    return GetPesosUseCase(db).execute()


@router.put("/pesos")
def atualizar_pesos(request: UpdatePesosRequest, _=Depends(require_pode_acessar_configuracoes_sabatina), db: Session = Depends(get_db)):
    try:
        return UpdatePesosUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.get("/eleicoes")
def listar_eleicoes(_=Depends(require_pode_acessar_configuracoes_sabatina), db: Session = Depends(get_db)):
    return ListEleicoesUseCase(db).execute()


@router.post("/eleicoes", status_code=201)
def criar_eleicao(
    request: EleicaoRequest, current_user=Depends(require_pode_acessar_configuracoes_sabatina), db: Session = Depends(get_db)
):
    try:
        return CreateEleicaoUseCase(db).execute(request, current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.get("/eleicoes/{eleicao_id}")
def get_eleicao(eleicao_id: int, _=Depends(require_pode_acessar_configuracoes_sabatina), db: Session = Depends(get_db)):
    try:
        return GetEleicaoUseCase(db).execute(eleicao_id)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.put("/eleicoes/{eleicao_id}")
def editar_eleicao(
    eleicao_id: int, request: EleicaoRequest, _=Depends(require_pode_acessar_configuracoes_sabatina), db: Session = Depends(get_db)
):
    try:
        return UpdateEleicaoUseCase(db).execute(eleicao_id, request)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.delete("/eleicoes/{eleicao_id}", status_code=204)
def apagar_eleicao(eleicao_id: int, _=Depends(require_pode_acessar_configuracoes_sabatina), db: Session = Depends(get_db)):
    try:
        DeleteEleicaoUseCase(db).execute(eleicao_id)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.post("/eleicoes/{eleicao_id}/abrir")
def abrir_eleicao(eleicao_id: int, _=Depends(require_pode_acessar_configuracoes_sabatina), db: Session = Depends(get_db)):
    try:
        return AbrirEleicaoUseCase(db).execute(eleicao_id)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.post("/eleicoes/{eleicao_id}/fechar")
def fechar_eleicao(eleicao_id: int, _=Depends(require_pode_acessar_configuracoes_sabatina), db: Session = Depends(get_db)):
    try:
        return FecharEleicaoUseCase(db).execute(eleicao_id)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.get("/eleicoes/{eleicao_id}/graficos")
def graficos_eleicao(eleicao_id: int, _=Depends(require_pode_acessar_configuracoes_sabatina), db: Session = Depends(get_db)):
    """Contagem agregada pra corrida ao vivo (aberta) e gráficos da apuração
    (fechada). Sem identidade de eleitor."""
    try:
        return GetGraficosEleicaoUseCase(db).execute(eleicao_id)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)
