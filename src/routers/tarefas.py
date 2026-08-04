"""Tarefas (kanban) e reuniões semanais — §6.4.

⚠ Nenhuma rota aqui usa `require_posicao`/`require_lideranca`. O §3 dá criar
e mover tarefa, e registrar reunião, aos **quatro** perfis. A única trava é
`exigir_acesso_ao_projeto` — que já é o recorte de visão da F2.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import exigir_acesso_ao_projeto, require_diretor
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.tarefa.colunas import (
    CreateColunaRequest,
    CreateColunaUseCase,
    DeleteColunaUseCase,
    ListColunasUseCase,
    ReordenarColunasRequest,
    ReordenarColunasUseCase,
    UpdateColunaRequest,
    UpdateColunaUseCase,
)
from src.repositories.tarefa_repository import ReuniaoSemanalRepository, TarefaRepository
from src.use_cases.tarefa.tarefas import (
    CreateReuniaoUseCase,
    CreateTarefaRequest,
    CreateTarefaUseCase,
    DeleteReuniaoUseCase,
    DeleteTarefaUseCase,
    ListReunioesUseCase,
    ListTarefasUseCase,
    ReuniaoRequest,
    UpdateReuniaoUseCase,
    UpdateTarefaRequest,
    UpdateTarefaUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(tags=["tarefas"], dependencies=[Depends(get_current_user)])


# ------------------------------------------------- colunas do kanban
#
# 🔒 Escrita só da diretoria (§3: "gerir" é dela). Leitura de todo mundo —
# o kanban de qualquer projeto precisa das colunas para desenhar o board.


@router.get("/tarefas-colunas")
def list_colunas(db: Session = Depends(get_db)):
    return ListColunasUseCase(db).execute()


@router.post("/tarefas-colunas")
def create_coluna(request: CreateColunaRequest, _=Depends(require_diretor), db: Session = Depends(get_db)):
    try:
        return CreateColunaUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/tarefas-colunas/{coluna_id}")
def update_coluna(coluna_id: int, request: UpdateColunaRequest, _=Depends(require_diretor), db: Session = Depends(get_db)):
    try:
        result = UpdateColunaUseCase(db).execute(coluna_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Coluna não encontrada")
    return result


@router.put("/tarefas-colunas/ordem")
def reordenar_colunas(request: ReordenarColunasRequest, _=Depends(require_diretor), db: Session = Depends(get_db)):
    try:
        return ReordenarColunasUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/tarefas-colunas/{coluna_id}", status_code=204)
def delete_coluna(coluna_id: int, mover_para: Optional[int] = None, _=Depends(require_diretor), db: Session = Depends(get_db)):
    """`?mover_para=` é obrigatório quando a coluna tem tarefas — elas nunca
    são apagadas junto."""
    try:
        apagada = DeleteColunaUseCase(db).execute(coluna_id, mover_para)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not apagada:
        raise HTTPException(status_code=404, detail="Coluna não encontrada")


def _acesso_pela_tarefa(tarefa_id: int, current_user, db: Session):
    tarefa = TarefaRepository(db).get_by_id(tarefa_id)
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    exigir_acesso_ao_projeto(tarefa.projeto_id, current_user, db)


def _acesso_pela_reuniao(reuniao_id: int, current_user, db: Session):
    reuniao = ReuniaoSemanalRepository(db).get_by_id(reuniao_id)
    if not reuniao:
        raise HTTPException(status_code=404, detail="Reunião não encontrada")
    exigir_acesso_ao_projeto(reuniao.projeto_id, current_user, db)


# ---------------------------------------------------------------- tarefas


@router.get("/projetos/{projeto_id}/tarefas")
def list_tarefas(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    return ListTarefasUseCase(db).execute(projeto_id)


@router.post("/projetos/{projeto_id}/tarefas")
def create_tarefa(projeto_id: int, request: CreateTarefaRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = CreateTarefaUseCase(db).execute(projeto_id, request, criado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/tarefas/{tarefa_id}")
def update_tarefa(tarefa_id: int, request: UpdateTarefaRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Move (arrastar no kanban) e edita — a mesma rota."""
    _acesso_pela_tarefa(tarefa_id, current_user, db)
    try:
        return UpdateTarefaUseCase(db).execute(tarefa_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/tarefas/{tarefa_id}", status_code=204)
def delete_tarefa(tarefa_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _acesso_pela_tarefa(tarefa_id, current_user, db)
    DeleteTarefaUseCase(db).execute(tarefa_id)


# ---------------------------------------------------------------- reuniões


@router.get("/projetos/{projeto_id}/reunioes")
def list_reunioes(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    return ListReunioesUseCase(db).execute(projeto_id)


@router.post("/projetos/{projeto_id}/reunioes")
def create_reuniao(projeto_id: int, request: ReuniaoRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = CreateReuniaoUseCase(db).execute(projeto_id, request, registrado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/reunioes/{reuniao_id}")
def update_reuniao(reuniao_id: int, request: ReuniaoRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Mover a reunião de dia — registrou quarta, aconteceu quinta."""
    _acesso_pela_reuniao(reuniao_id, current_user, db)
    try:
        return UpdateReuniaoUseCase(db).execute(reuniao_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/reunioes/{reuniao_id}", status_code=204)
def delete_reuniao(reuniao_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _acesso_pela_reuniao(reuniao_id, current_user, db)
    DeleteReuniaoUseCase(db).execute(reuniao_id)
