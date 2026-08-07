"""Monitoramento da diretoria e gerência (§7).

🔐 A maioria das rotas fica atrás de `require_gestao` (diretor + gerente);
`/tarefas` é a exceção, `require_diretor` só — é o board macro de tarefas de
todos os projetos, mais informal que os números agregados das outras abas.
Todo use case abre com `aplicar_recorte_visao`, que já é o §7.5 de graça: o
gerente fica travado nas próprias frentes mesmo mandando outro `?frente_id=`.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.use_cases.monitoramento.graficos import MontarGraficoUseCase, listar_fontes
from src.utils.exceptions import RegraDeNegocioError
from src.middlewares.authorization import require_diretor, require_pode_ver_monitoramento
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.monitoramento.monitoramento import (
    AlocacaoUseCase,
    AtrasosUseCase,
    CronogramasGeraisUseCase,
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
def execucao(
    frente_id: Optional[int] = None,
    referencia: Optional[date] = None,
    current_user=Depends(require_pode_ver_monitoramento),
    db: Session = Depends(get_db),
):
    """`referencia` = qualquer dia da semana que se quer ver; sem ela, hoje.

    Só o PASSADO é aceito. Semana futura devolveria "não distribuiu" e "não
    fez reunião" para todo mundo — as duas medem ausência de registro, e no
    futuro ausência significa "ainda não aconteceu", não "o time falhou". A
    tela acusaria o time por algo que ainda nem teve chance de existir.
    """
    if referencia and referencia > date.today():
        raise HTTPException(
            status_code=422, detail="Só é possível consultar a semana atual ou anteriores"
        )
    return ExecucaoUseCase(db).execute(current_user, frente_id, referencia)


@router.get("/alocacao")
def alocacao(frente_id: Optional[int] = None, current_user=Depends(require_pode_ver_monitoramento), db: Session = Depends(get_db)):
    return AlocacaoUseCase(db).execute(current_user, frente_id)


@router.get("/atrasos")
def atrasos(frente_id: Optional[int] = None, current_user=Depends(require_pode_ver_monitoramento), db: Session = Depends(get_db)):
    return AtrasosUseCase(db).execute(current_user, frente_id)


@router.get("/tarefas")
def tarefas(frente_id: Optional[int] = None, current_user=Depends(require_diretor), db: Session = Depends(get_db)):
    return TarefasGeraisUseCase(db).execute(current_user, frente_id)


@router.get("/cronogramas")
def cronogramas(frente_id: Optional[int] = None, current_user=Depends(require_diretor), db: Session = Depends(get_db)):
    return CronogramasGeraisUseCase(db).execute(current_user, frente_id)


@router.get("/graficos/fontes")
def graficos_fontes(_=Depends(require_pode_ver_monitoramento)):
    """As tabelas liberadas para montar gráfico, com descrição e colunas.

    A lista é curada à mão em `graficos.py` — ver o aviso de segurança no topo
    daquele arquivo antes de acrescentar tabela.
    """
    return listar_fontes()


@router.get("/graficos/dados")
def graficos_dados(
    tabela: str,
    dimensao: str,
    operacao: str = "contagem",
    metrica: Optional[str] = None,
    granularidade: str = "mes",
    _=Depends(require_pode_ver_monitoramento),
    db: Session = Depends(get_db),
):
    """Agrega e devolve os pontos do gráfico.

    ⚠ `tabela`, `dimensao` e `metrica` chegam como texto da requisição, mas
    NUNCA entram em SQL: o use case procura cada um no catálogo e trabalha com
    os objetos Column resolvidos. O que não estiver lá é recusado com 422.
    """
    try:
        return MontarGraficoUseCase(db).execute(tabela, dimensao, operacao, metrica, granularidade)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
