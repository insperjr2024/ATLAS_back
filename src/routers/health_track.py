"""Health Track — a saúde dos projetos, pilar a pilar (§2 a §5 da spec).

Pilares, as cores de cada pilar por projeto, o status geral calculado a partir
delas (§4) e a regra desse cálculo, editável e versionada (§5).

Ler segue o recorte de visão de sempre (quem enxerga o projeto, inclusive
quem só o vendeu). Preencher é da diretoria de projetos e do gerente de uma
frente do projeto — ver `exigir_pode_preencher_health_track`. A regra do
status geral se lê por qualquer pessoa logada e só a diretoria de projetos
edita.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    exigir_acesso_ao_projeto,
    exigir_pode_preencher_health_track,
    pode_preencher_health_track,
    require_diretor_projetos,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.health_track.get_avaliacao_atual import GetAvaliacaoAtualUseCase
from src.use_cases.health_track.get_ciclos import GetCiclosUseCase
from src.use_cases.health_track.get_historico import GetHistoricoUseCase
from src.use_cases.health_track.get_regra import GetHistoricoRegraUseCase, GetRegraUseCase
from src.use_cases.health_track.listar_classificacoes import ListarClassificacoesUseCase
from src.use_cases.health_track.listar_pilares import ListarPilaresUseCase
from src.use_cases.health_track.registrar_avaliacao import (
    RegistrarAvaliacaoRequest,
    RegistrarAvaliacaoUseCase,
)
from src.use_cases.health_track.update_regra import UpdateRegraRequest, UpdateRegraUseCase
from src.utils.erro_http import erro_de_regra
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(
    prefix="/health-track", tags=["health track"], dependencies=[Depends(get_current_user)]
)


@router.get("/pilares")
def listar_pilares(db: Session = Depends(get_db)):
    return ListarPilaresUseCase(db).execute()


@router.get("/classificacoes")
def listar_classificacoes():
    return ListarClassificacoesUseCase().execute()


@router.post("/projetos/{projeto_id}/avaliacoes", status_code=201)
def registrar_avaliacao(
    projeto_id: int,
    request: RegistrarAvaliacaoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exigir_pode_preencher_health_track(projeto_id, current_user, db)
    try:
        return RegistrarAvaliacaoUseCase(db).execute(projeto_id, request, current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.get("/projetos/{projeto_id}/avaliacoes/atual")
def avaliacao_atual(
    projeto_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exigir_acesso_ao_projeto(projeto_id, current_user, db, somente_leitura_ok=True)
    return {
        **GetAvaliacaoAtualUseCase(db).execute(projeto_id),
        "pode_preencher": pode_preencher_health_track(projeto_id, current_user, db),
    }


@router.get("/projetos/{projeto_id}/avaliacoes/historico")
def historico(
    projeto_id: int,
    pilar_id: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exigir_acesso_ao_projeto(projeto_id, current_user, db, somente_leitura_ok=True)
    return GetHistoricoUseCase(db).execute(projeto_id, pilar_id)


@router.get("/projetos/{projeto_id}/avaliacoes/ciclos")
def ciclos(
    projeto_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exigir_acesso_ao_projeto(projeto_id, current_user, db, somente_leitura_ok=True)
    return GetCiclosUseCase(db).execute(projeto_id)


@router.get("/regra")
def regra(db: Session = Depends(get_db)):
    return GetRegraUseCase(db).execute()


@router.put("/regra")
def atualizar_regra(
    request: UpdateRegraRequest,
    current_user=Depends(require_diretor_projetos),
    db: Session = Depends(get_db),
):
    try:
        return UpdateRegraUseCase(db).execute(request, current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.get("/regra/historico")
def historico_regra(db: Session = Depends(get_db)):
    return GetHistoricoRegraUseCase(db).execute()
