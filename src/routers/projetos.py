"""O núcleo da Prioridade 1: Projeto → equipe → status (§4, §6.3, §6.4)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    exigir_acesso_ao_projeto,
    require_gestao,
    require_lideranca,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.projeto.create_projeto import CreateProjetoUseCase, CreateProjetoRequest
from src.use_cases.projeto.get_projeto import (
    GetHistoricoProjetoUseCase,
    GetProjetoUseCase,
    ListProjetosUseCase,
)
from src.use_cases.projeto.update_equipe_projeto import (
    UpdateEquipeProjetoUseCase,
    UpdateEquipeProjetoRequest,
)
from src.use_cases.projeto.update_kickoff import (
    UpdateEntregaClienteRequest,
    UpdateEntregaClienteUseCase,
    UpdateKickoffRequest,
    UpdateKickoffUseCase,
)
from src.use_cases.projeto.update_status import UpdateStatusRequest, UpdateStatusUseCase
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(tags=["projetos"], dependencies=[Depends(get_current_user)])


@router.post("/projetos")
def create_projeto(request: CreateProjetoRequest, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    try:
        return CreateProjetoUseCase(db).execute(request, criado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/projetos")
def list_projetos(frente_id: Optional[int] = None, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ListProjetosUseCase(db).execute(current_user, frente_id=frente_id)


@router.get("/projetos/{projeto_id}")
def get_projeto(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    result = GetProjetoUseCase(db).execute(projeto_id)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.put("/projetos/{projeto_id}/equipe")
def update_equipe(projeto_id: int, request: UpdateEquipeProjetoRequest, _=Depends(require_gestao), db: Session = Depends(get_db)):
    try:
        result = UpdateEquipeProjetoUseCase(db).execute(projeto_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/projetos/{projeto_id}/kickoff")
def update_kickoff(projeto_id: int, request: UpdateKickoffRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = UpdateKickoffUseCase(db).execute(projeto_id, request, alterado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/projetos/{projeto_id}/entrega-cliente")
def update_entrega_cliente(projeto_id: int, request: UpdateEntregaClienteRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    result = UpdateEntregaClienteUseCase(db).execute(projeto_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/projetos/{projeto_id}/status")
def update_status(projeto_id: int, request: UpdateStatusRequest, current_user=Depends(require_lideranca), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = UpdateStatusUseCase(db).execute(projeto_id, request, alterado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.get("/projetos/{projeto_id}/historico")
def get_historico(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    return GetHistoricoProjetoUseCase(db).execute(projeto_id)
