"""Tarefas (kanban) e reuniões semanais — §6.4.

⚠ Nenhuma rota aqui usa `require_posicao`/`require_lideranca`. O §3 dá criar
e mover tarefa, e registrar reunião, aos **quatro** perfis. A única trava é
`exigir_acesso_ao_projeto` — que já é o recorte de visão da F2.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    eh_diretoria_de_projetos,
    exigir_acesso_ao_projeto,
    require_diretor_projetos,
    require_pode_criar_tarefa,
    require_pode_mover_editar_tarefa,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.tarefa.comentarios import (
    ComentarioRequest,
    CreateComentarioUseCase,
    DeleteComentarioUseCase,
    ListComentariosUseCase,
    pode_editar_tarefa,
)
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
from src.repositories.tarefa_coluna_repository import TarefaColunaRepository
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
# 🔒 Escrita só da diretoria (§3: "gerir" é dela). Leitura de quem enxerga o
# projeto — o kanban precisa das colunas para desenhar o board.
#
# ⚠ As colunas são **do projeto**, não globais: a diretora ajusta o fluxo de
# um projeto sem mexer nos outros. Por isso toda rota está sob
# `/projetos/{projeto_id}`, e as que recebem `coluna_id` conferem que a
# coluna é daquele projeto (senão bastaria adivinhar um id para editar o
# board alheio).


def _coluna_do_projeto(projeto_id: int, coluna_id: int, db: Session):
    coluna = TarefaColunaRepository(db).get_by_id(coluna_id)
    if not coluna or coluna.projeto_id != projeto_id:
        raise HTTPException(status_code=404, detail="Coluna não encontrada")


@router.get("/projetos/{projeto_id}/tarefas-colunas")
def list_colunas(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db, somente_leitura_ok=True)
    return ListColunasUseCase(db).execute(projeto_id)


@router.post("/projetos/{projeto_id}/tarefas-colunas")
def create_coluna(projeto_id: int, request: CreateColunaRequest, current_user=Depends(require_diretor_projetos), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        return CreateColunaUseCase(db).execute(projeto_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.put("/projetos/{projeto_id}/tarefas-colunas/ordem")
def reordenar_colunas(projeto_id: int, request: ReordenarColunasRequest, current_user=Depends(require_diretor_projetos), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        return ReordenarColunasUseCase(db).execute(projeto_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/projetos/{projeto_id}/tarefas-colunas/{coluna_id}")
def update_coluna(projeto_id: int, coluna_id: int, request: UpdateColunaRequest, current_user=Depends(require_diretor_projetos), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    _coluna_do_projeto(projeto_id, coluna_id, db)
    try:
        result = UpdateColunaUseCase(db).execute(coluna_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Coluna não encontrada")
    return result


@router.delete("/projetos/{projeto_id}/tarefas-colunas/{coluna_id}", status_code=204)
def delete_coluna(projeto_id: int, coluna_id: int, mover_para: Optional[int] = None, current_user=Depends(require_diretor_projetos), db: Session = Depends(get_db)):
    """`?mover_para=` é obrigatório quando a coluna tem tarefas — elas nunca
    são apagadas junto."""
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    _coluna_do_projeto(projeto_id, coluna_id, db)
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
    exigir_acesso_ao_projeto(projeto_id, current_user, db, somente_leitura_ok=True)
    return ListTarefasUseCase(db).execute(projeto_id)


@router.post("/projetos/{projeto_id}/tarefas")
def create_tarefa(projeto_id: int, request: CreateTarefaRequest, current_user=Depends(require_pode_criar_tarefa), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = CreateTarefaUseCase(db).execute(projeto_id, request, criado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/tarefas/{tarefa_id}")
def update_tarefa(tarefa_id: int, request: UpdateTarefaRequest, current_user=Depends(require_pode_mover_editar_tarefa), db: Session = Depends(get_db)):
    """Move (arrastar no kanban) e edita — a mesma rota."""
    _acesso_pela_tarefa(tarefa_id, current_user, db)
    try:
        return UpdateTarefaUseCase(db).execute(tarefa_id, request, current_user)
    except RegraDeNegocioError as e:
        # Falta de permissão de edição vem como regra de negócio do use case;
        # aqui vira 403, que é o código que a tela espera para esconder o form.
        codigo = 403 if "podem editá-la" in str(e) else 422
        raise HTTPException(status_code=codigo, detail=str(e))


@router.delete("/tarefas/{tarefa_id}", status_code=204)
def delete_tarefa(tarefa_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Excluir é destrutivo: mesma régua da edição (diretoria ou quem criou)."""
    tarefa = TarefaRepository(db).get_by_id(tarefa_id)
    if not tarefa:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    exigir_acesso_ao_projeto(tarefa.projeto_id, current_user, db)
    if not pode_editar_tarefa(tarefa, current_user):
        raise HTTPException(
            status_code=403,
            detail="Só a diretoria e quem criou a tarefa podem excluí-la",
        )
    DeleteTarefaUseCase(db).execute(tarefa_id)


# ---------------------------------------------------------------- comentários


@router.get("/tarefas/{tarefa_id}/comentarios")
def list_comentarios(tarefa_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _acesso_pela_tarefa(tarefa_id, current_user, db)
    return ListComentariosUseCase(db).execute(tarefa_id)


@router.post("/tarefas/{tarefa_id}/comentarios")
def create_comentario(tarefa_id: int, request: ComentarioRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Comentar é de quem enxerga o projeto — discutir a tarefa é trabalho de
    equipe, não privilégio de quem a criou."""
    _acesso_pela_tarefa(tarefa_id, current_user, db)
    try:
        result = CreateComentarioUseCase(db).execute(tarefa_id, request, current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    return result


@router.delete("/comentarios/{comentario_id}", status_code=204)
def delete_comentario(comentario_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    from src.use_cases.tarefa.comentarios import TarefaComentarioRepository

    comentario = TarefaComentarioRepository(db).get_by_id(comentario_id)
    if not comentario:
        raise HTTPException(status_code=404, detail="Comentário não encontrado")
    tarefa = TarefaRepository(db).get_by_id(comentario.tarefa_id)
    exigir_acesso_ao_projeto(tarefa.projeto_id, current_user, db)
    try:
        DeleteComentarioUseCase(db).execute(comentario_id, current_user)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ---------------------------------------------------------------- reuniões


@router.get("/projetos/{projeto_id}/reunioes")
def list_reunioes(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db, somente_leitura_ok=True)
    return ListReunioesUseCase(db).execute(projeto_id)


@router.post("/projetos/{projeto_id}/reunioes")
def create_reuniao(projeto_id: int, request: ReuniaoRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """⭐ Registrar a reunião da semana — e sobre qual escopo ela foi.

    Quando é a PRIMEIRA reunião de um escopo, é esta chamada que preenche
    `projeto_escopo.data_inicio` e faz a contagem do §5.4 começar a correr.
    """
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
    """Mover a reunião de dia — registrou quarta, aconteceu quinta — ou
    corrigir sobre qual escopo ela foi. A `data_inicio` do escopo acompanha.

    Mover a reunião INICIAL **poda o cronograma do escopo** — o que não cabe
    na janela nova é apagado, o resto fica —, e por isso continua sendo decisão
    da diretoria: o `eh_diretor_projetos` abaixo é o que separa quem executa de
    quem precisa pedir.
    """
    _acesso_pela_reuniao(reuniao_id, current_user, db)
    try:
        return UpdateReuniaoUseCase(db).execute(
            reuniao_id, request, eh_diretor_projetos=eh_diretoria_de_projetos(current_user)
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/reunioes/{reuniao_id}", status_code=204)
def delete_reuniao(reuniao_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _acesso_pela_reuniao(reuniao_id, current_user, db)
    DeleteReuniaoUseCase(db).execute(reuniao_id)
