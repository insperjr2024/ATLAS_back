"""Monitoramento da diretoria e gerência (§7).

🔐 Todas as rotas atrás de `require_gestao` (diretor + gerente), e cada use
case abre com `aplicar_recorte_visao` — que já é o §7.5 de graça: o gerente
fica travado nas próprias frentes mesmo mandando outro `?frente_id=`.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import require_gestao
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.monitoramento.monitoramento import (
    AlocacaoUseCase,
    AtrasosUseCase,
    ExecucaoUseCase,
    VisaoGeralUseCase,
)

router = APIRouter(
    prefix="/monitoramento", tags=["monitoramento"], dependencies=[Depends(get_current_user)]
)


@router.get("/visao-geral")
def visao_geral(frente_id: Optional[int] = None, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    return VisaoGeralUseCase(db).execute(current_user, frente_id)


@router.get("/execucao")
def execucao(frente_id: Optional[int] = None, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    return ExecucaoUseCase(db).execute(current_user, frente_id)


@router.get("/alocacao")
def alocacao(frente_id: Optional[int] = None, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    return AlocacaoUseCase(db).execute(current_user, frente_id)


@router.get("/atrasos")
def atrasos(frente_id: Optional[int] = None, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    return AtrasosUseCase(db).execute(current_user, frente_id)
