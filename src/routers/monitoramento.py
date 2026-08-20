"""Monitoramento da diretoria e gerência (§7).

🔐 A maioria das rotas fica atrás de `require_gestao` (diretor + gerente);
`/tarefas` é a exceção, `require_diretor` só — é o board macro de tarefas de
todos os projetos, mais informal que os números agregados das outras abas.
Todo use case abre com `aplicar_recorte_visao`, que já é o §7.5 de graça: o
gerente fica travado nas próprias frentes mesmo mandando outro `?frente_id=`.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.use_cases.monitoramento.graficos import MontarGraficoUseCase, listar_fontes
from src.utils.exceptions import RegraDeNegocioError
from src.middlewares.authorization import (
    require_diretor,
    require_gestao,
    require_pode_ver_monitoramento,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.monitoramento.aprovacoes import ListarAprovacoesPendentesUseCase
from src.use_cases.monitoramento.historico_projetos import HistoricoProjetosUseCase
from src.use_cases.monitoramento.projetos_ativos import ProjetosAtivosUseCase
from src.use_cases.monitoramento.monitoramento import (
    AlocacaoUseCase,
    AtrasosUseCase,
    CronogramasGeraisUseCase,
    ExecucaoUseCase,
    TarefasGeraisUseCase,
    VisaoGeralUseCase,
)
from src.utils.status_projeto import STATUS_VALIDOS

router = APIRouter(
    prefix="/monitoramento", tags=["monitoramento"], dependencies=[Depends(get_current_user)]
)


def filtro_status(
    status: Optional[List[str]] = Query(
        None,
        description=(
            "Etapas do ciclo de vida a manter. Repetir o parâmetro soma etapas: "
            "`?status=ambientacao&status=em_andamento`. Ausente = todas."
        ),
    ),
) -> Optional[List[str]]:
    """⭐ O filtro de status, compartilhado por todas as abas de números.

    Uma dependência só, e não uma validação copiada em cada rota, porque o
    valor errado precisa dar a MESMA resposta em todas — o seletor da tela é
    o mesmo componente, e um `?status=` que passa numa aba e falha em outra
    vira bug de "só a Alocação está quebrada".

    Recusa com 422 em vez de ignorar o desconhecido: filtro ignorado devolve
    o portfólio inteiro com o seletor marcado na tela, e quem olha lê o número
    do núcleo achando que é o da etapa. Vazio é diferente de errado — o §4 não
    tem etapa `em_progresso`, e dizer isso é mais honesto que uma tela cheia.
    """
    if not status:
        return None
    invalidos = [s for s in status if s not in STATUS_VALIDOS]
    if invalidos:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Status inválido: {', '.join(invalidos)}. "
                f"Valores aceitos: {', '.join(STATUS_VALIDOS)}"
            ),
        )
    # `dict.fromkeys` e não `set`: tira o repetido preservando a ordem em que
    # a pessoa marcou. A ordem não muda o resultado do `IN`, mas mantém a URL
    # estável entre requisições iguais — o que deixa o cache do navegador e os
    # logs legíveis.
    return list(dict.fromkeys(status))


@router.get("/visao-geral")
def visao_geral(
    frente_id: Optional[int] = None,
    escopo_id: Optional[int] = None,
    status: Optional[List[str]] = Depends(filtro_status),
    current_user=Depends(require_pode_ver_monitoramento),
    db: Session = Depends(get_db),
):
    return VisaoGeralUseCase(db).execute(current_user, frente_id, escopo_id=escopo_id, status=status)


@router.get("/execucao")
def execucao(
    frente_id: Optional[int] = None,
    referencia: Optional[date] = None,
    escopo_id: Optional[int] = None,
    status: Optional[List[str]] = Depends(filtro_status),
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
    return ExecucaoUseCase(db).execute(
        current_user, frente_id, referencia, escopo_id=escopo_id, status=status
    )


@router.get("/alocacao")
def alocacao(
    frente_id: Optional[int] = None,
    escopo_id: Optional[int] = None,
    status: Optional[List[str]] = Depends(filtro_status),
    current_user=Depends(require_pode_ver_monitoramento),
    db: Session = Depends(get_db),
):
    return AlocacaoUseCase(db).execute(current_user, frente_id, escopo_id=escopo_id, status=status)


@router.get("/atrasos")
def atrasos(
    frente_id: Optional[int] = None,
    escopo_id: Optional[int] = None,
    status: Optional[List[str]] = Depends(filtro_status),
    current_user=Depends(require_pode_ver_monitoramento),
    db: Session = Depends(get_db),
):
    return AtrasosUseCase(db).execute(current_user, frente_id, escopo_id=escopo_id, status=status)


@router.get("/aprovacoes")
def aprovacoes(current_user=Depends(require_diretor), db: Session = Depends(get_db)):
    """⭐ Tudo que espera uma decisão da diretoria, num lugar só.

    Sem `frente_id`: a fila é dela, e ela enxerga a área inteira (§3). Filtrar
    por frente aqui só criaria a chance de um pedido ficar escondido atrás de
    um filtro que alguém esqueceu ligado.
    """
    # `current_user` entra por causa das solicitações de entrada: quem pode
    # responder cada uma depende de quem está olhando (§3).
    return ListarAprovacoesPendentesUseCase(db).execute(current_user)


@router.get("/tarefas")
def tarefas(
    frente_id: Optional[int] = None,
    escopo_id: Optional[int] = None,
    status: Optional[List[str]] = Depends(filtro_status),
    current_user=Depends(require_diretor),
    db: Session = Depends(get_db),
):
    return TarefasGeraisUseCase(db).execute(
        current_user, frente_id, escopo_id=escopo_id, status=status
    )


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
        
@router.get("/cronogramas")
def cronogramas(
    frente_id: Optional[int] = None,
    escopo_id: Optional[int] = None,
    status: Optional[List[str]] = Depends(filtro_status),
    current_user=Depends(require_diretor),
    db: Session = Depends(get_db),
):
    return CronogramasGeraisUseCase(db).execute(
        current_user, frente_id, escopo_id=escopo_id, status=status
    )


@router.get("/projetos-ativos")
def projetos_ativos(
    frente_id: Optional[int] = None,
    status: Optional[List[str]] = Depends(filtro_status),
    current_user=Depends(require_pode_ver_monitoramento),
    db: Session = Depends(get_db),
):
    """A aba Projetos ativos: o retrato dos projetos em curso (não finalizados
    nem arquivados), com o mesmo recorte de visão do resto do painel."""
    return ProjetosAtivosUseCase(db).execute(current_user, frente_id, status=status)


@router.get("/historico-projetos")
def historico_projetos(
    frente_id: Optional[int] = None,
    filtro: str = "todos",
    current_user=Depends(require_gestao),
    db: Session = Depends(get_db),
):
    """A aba Histórico de projetos: o portfólio ENCERRADO (finalizado ou
    arquivado), só para diretoria e gerência.

    `require_gestao` trava por posição (diretor + gerente); o use case ainda
    aplica o recorte de visão (§7.5), então o gerente vê só o histórico das
    frentes dele. `filtro` ∈ {todos, finalizados, arquivados}.
    """
    return HistoricoProjetosUseCase(db).execute(current_user, frente_id, filtro=filtro)
