"""O cronograma pintado (§6.4) — etapas, marcos e oficialização.

Toda rota resolve o projeto (subindo etapa → escopo → projeto quando é rota
de detalhe) e passa por `exigir_acesso_ao_projeto`, que devolve 404 e não 403:
quem não enxerga o projeto não deve nem saber que ele existe.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import exigir_acesso_ao_projeto, require_lideranca
from src.middlewares.validate_user_auth_token import get_current_user
from src.repositories.cronograma_repository import (
    CronogramaEtapaRepository,
    CronogramaMarcoRepository,
)
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.use_cases.cronograma.get_cronograma import GetCronogramaUseCase
from src.use_cases.cronograma.update_cronograma import (
    CreateEtapaUseCase,
    CreateMarcoUseCase,
    DeleteEtapaUseCase,
    DeleteMarcoUseCase,
    EtapaDetalheRequest,
    EtapaIntervaloRequest,
    EtapaRequest,
    MarcoRequest,
    OficializarCronogramaUseCase,
    UpdateEtapaDetalheUseCase,
    UpdateEtapaIntervaloUseCase,
)
from src.utils.cronograma_guard import CronogramaOficializadoError, http_conflito_cronograma
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(tags=["cronograma"], dependencies=[Depends(get_current_user)])


def _projeto_do_escopo(escopo_id: int, current_user, db: Session) -> int:
    escopo = ProjetoEscopoRepository(db).get_by_id(escopo_id)
    if not escopo:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    exigir_acesso_ao_projeto(escopo.projeto_id, current_user, db)
    return escopo.projeto_id


def _projeto_da_etapa(etapa_id: int, current_user, db: Session) -> int:
    etapa = CronogramaEtapaRepository(db).get_by_id(etapa_id)
    if not etapa:
        raise HTTPException(status_code=404, detail="Etapa não encontrada")
    return _projeto_do_escopo(etapa.projeto_escopo_id, current_user, db)


def _executar(acao):
    """Traduz as duas exceções de domínio nos códigos certos.

    409 (conflito de estado) para cronograma oficializado, 422 para regra de
    negócio — o front usa a diferença para oferecer "solicitar reajuste" em
    vez de um erro genérico.
    """
    try:
        return acao()
    except CronogramaOficializadoError:
        raise http_conflito_cronograma()
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/projetos/{projeto_id}/cronograma")
def get_cronograma(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """A aba inteira numa ida só: escopos + etapas + marcos + faixas
    derivadas + os dias cinzas já resolvidos para a janela."""
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    result = GetCronogramaUseCase(db).execute(projeto_id)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.post("/escopos-projeto/{escopo_id}/etapas")
def create_etapa(escopo_id: int, request: EtapaRequest, current_user=Depends(require_lideranca), db: Session = Depends(get_db)):
    _projeto_do_escopo(escopo_id, current_user, db)
    result = _executar(lambda: CreateEtapaUseCase(db).execute(escopo_id, request, current_user.id))
    if not result:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return result


@router.put("/cronograma/etapas/{etapa_id}")
def update_etapa_intervalo(etapa_id: int, request: EtapaIntervaloRequest, current_user=Depends(require_lideranca), db: Session = Depends(get_db)):
    """⭐ É esta que o arrasto chama — um gesto, uma requisição, por intervalo."""
    _projeto_da_etapa(etapa_id, current_user, db)
    result = _executar(lambda: UpdateEtapaIntervaloUseCase(db).execute(etapa_id, request))
    if not result:
        raise HTTPException(status_code=404, detail="Etapa não encontrada")
    return result


@router.patch("/cronograma/etapas/{etapa_id}")
def update_etapa_detalhe(etapa_id: int, request: EtapaDetalheRequest, current_user=Depends(require_lideranca), db: Session = Depends(get_db)):
    _projeto_da_etapa(etapa_id, current_user, db)
    result = _executar(lambda: UpdateEtapaDetalheUseCase(db).execute(etapa_id, request))
    if not result:
        raise HTTPException(status_code=404, detail="Etapa não encontrada")
    return result


@router.delete("/cronograma/etapas/{etapa_id}", status_code=204)
def delete_etapa(etapa_id: int, current_user=Depends(require_lideranca), db: Session = Depends(get_db)):
    _projeto_da_etapa(etapa_id, current_user, db)
    _executar(lambda: DeleteEtapaUseCase(db).execute(etapa_id))


@router.post("/projetos/{projeto_id}/marcos")
def create_marco(projeto_id: int, request: MarcoRequest, current_user=Depends(require_lideranca), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    return _executar(lambda: CreateMarcoUseCase(db).execute(projeto_id, request, current_user.id))


@router.delete("/cronograma/marcos/{marco_id}", status_code=204)
def delete_marco(marco_id: int, current_user=Depends(require_lideranca), db: Session = Depends(get_db)):
    marco = CronogramaMarcoRepository(db).get_by_id(marco_id)
    if not marco:
        raise HTTPException(status_code=404, detail="Marco não encontrado")
    exigir_acesso_ao_projeto(marco.projeto_id, current_user, db)
    DeleteMarcoUseCase(db).execute(marco_id)


@router.post("/escopos-projeto/{escopo_id}/oficializar")
def oficializar(escopo_id: int, current_user=Depends(require_lideranca), db: Session = Depends(get_db)):
    """§5.3: cravar o cronograma. Depois disso, mudar exige reajuste (§5.6)."""
    _projeto_do_escopo(escopo_id, current_user, db)
    result = _executar(lambda: OficializarCronogramaUseCase(db).execute(escopo_id))
    if not result:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return result
