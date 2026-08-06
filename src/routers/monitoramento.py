"""Monitoramento da diretoria e gerência (§7).

🔐 A maioria das rotas fica atrás de `require_gestao` (diretor + gerente);
`/tarefas` é a exceção, `require_diretor` só — é o board macro de tarefas de
todos os projetos, mais informal que os números agregados das outras abas.
Todo use case abre com `aplicar_recorte_visao`, que já é o §7.5 de graça: o
gerente fica travado nas próprias frentes mesmo mandando outro `?frente_id=`.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import require_diretor, require_pode_ver_monitoramento
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.monitoramento.monitoramento import (
    AlocacaoUseCase,
    AtrasosUseCase,
    ExecucaoUseCase,
    TarefasGeraisUseCase,
    VisaoGeralUseCase,
)

router = APIRouter(
    prefix="/monitoramento", tags=["monitoramento"], dependencies=[Depends(get_current_user)]
)


@router.get("/visao-geral")
def visao_geral(frente_id: Optional[int] = None, current_user=Depends(require_pode_ver_monitoramento), db: Session = Depends(get_db)):
    return VisaoGeralUseCase(db).execute(current_user, frente_id)


@router.get("/execucao")
def execucao(frente_id: Optional[int] = None, current_user=Depends(require_pode_ver_monitoramento), db: Session = Depends(get_db)):
    return ExecucaoUseCase(db).execute(current_user, frente_id)


@router.get("/alocacao")
def alocacao(frente_id: Optional[int] = None, current_user=Depends(require_pode_ver_monitoramento), db: Session = Depends(get_db)):
    return AlocacaoUseCase(db).execute(current_user, frente_id)


@router.get("/atrasos")
def atrasos(frente_id: Optional[int] = None, current_user=Depends(require_pode_ver_monitoramento), db: Session = Depends(get_db)):
    return AtrasosUseCase(db).execute(current_user, frente_id)


@router.get("/tarefas")
def tarefas(frente_id: Optional[int] = None, current_user=Depends(require_diretor), db: Session = Depends(get_db)):
    return TarefasGeraisUseCase(db).execute(current_user, frente_id)
