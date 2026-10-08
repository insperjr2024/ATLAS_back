"""Health Track — a saúde dos projetos, pilar a pilar (§2 a §5 da spec).

Pilares, as cores de cada pilar por projeto, o status geral calculado a partir
delas (§4) e a regra desse cálculo, editável e versionada (§5).

O router INTEIRO exige a caixa `pode_ver_health_track`, que nasce só no
diretor de projetos (2026-10-07/08, a pedido da diretoria: coordenador e
consultor não veem o Health Track, que por isso saiu de dentro do projeto e
virou página própria). Por baixo dela valem as regras de antes: ler a
avaliação segue o recorte de visão (quem enxerga o projeto), preencher é da
diretoria de projetos e do gerente de uma frente do projeto (ver
`exigir_pode_preencher_health_track`), e editar a regra do status geral e
os pilares é só da diretoria de projetos. Dar a caixa a outra posição abre a
leitura; não abre nem preenchimento nem edição.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    exigir_acesso_ao_projeto,
    exigir_pode_preencher_health_track,
    pode_preencher_health_track,
    require_diretor_projetos,
    require_pode_ver_health_track,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.health_track.acoes import (
    AcaoRequest,
    ApagarAcaoUseCase,
    ConcluirAcaoUseCase,
    ConcluirMinhaAcaoUseCase,
    ListMinhasAcoesUseCase,
    CriarAcaoUseCase,
    EditarAcaoUseCase,
    ListAcoesAbertasUseCase,
    ListAcoesDoProjetoUseCase,
)
from src.use_cases.health_track.apagar import ApagarCicloUseCase, ZerarHealthTrackUseCase
from src.use_cases.health_track.editar_pilares import (
    CriarPilarUseCase,
    EditarPilarRequest,
    EditarPilarUseCase,
    ListarTodosPilaresUseCase,
    PilarRequest,
)
from src.use_cases.health_track.get_avaliacao_atual import GetAvaliacaoAtualUseCase
from src.use_cases.health_track.get_carteira import GetCarteiraUseCase
from src.use_cases.health_track.get_evolucao import GetEvolucaoUseCase
from src.use_cases.health_track.get_ciclos import GetCiclosUseCase
from src.use_cases.health_track.get_historico import GetHistoricoUseCase
from src.use_cases.health_track.get_regra import GetHistoricoRegraUseCase, GetRegraUseCase
from src.use_cases.health_track.listar_classificacoes import ListarClassificacoesUseCase
from src.use_cases.health_track.listar_pilares import ListarPilaresUseCase
from src.use_cases.health_track.rodadas import (
    AbrirRodadaUseCase,
    ConcluirRodadaUseCase,
    DesfazerJustificativaUseCase,
    GetRodadaAtualUseCase,
    JustificarProjetoUseCase,
    JustificarRequest,
    ListRodadasUseCase,
)
from src.use_cases.health_track.registrar_avaliacao import (
    RegistrarAvaliacaoRequest,
    RegistrarAvaliacaoUseCase,
)
from src.use_cases.health_track.update_regra import UpdateRegraRequest, UpdateRegraUseCase
from src.utils.erro_http import erro_de_regra
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(
    prefix="/health-track",
    tags=["health track"],
    dependencies=[Depends(require_pode_ver_health_track)],
)


@router.get("/carteira")
def carteira(
    frente_id: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """O mapa da carteira (§8 e §9): projetos em curso que a pessoa enxerga,
    com a cor de cada pilar e o status geral."""
    return GetCarteiraUseCase(db).execute(current_user, frente_id)


# ---------------------------------------------------------------- rodadas
#
# Abrir, concluir, justificar e desfazer: diretoria de projetos, a dona do
# ritmo. Ler: qualquer um com a caixa (o gerente vê o que falta na frente
# dele e avalia pelo painel do projeto, que marca o item sozinho).


@router.get("/rodadas")
def listar_rodadas(db: Session = Depends(get_db)):
    return ListRodadasUseCase(db).execute()


@router.get("/rodadas/atual")
def rodada_atual(db: Session = Depends(get_db)):
    return GetRodadaAtualUseCase(db).execute()


@router.post("/rodadas", status_code=201)
def abrir_rodada(current_user=Depends(require_diretor_projetos), db: Session = Depends(get_db)):
    try:
        return AbrirRodadaUseCase(db).execute(current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.post("/rodadas/{rodada_id}/concluir")
def concluir_rodada(rodada_id: int, current_user=Depends(require_diretor_projetos), db: Session = Depends(get_db)):
    try:
        return ConcluirRodadaUseCase(db).execute(rodada_id, current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.put("/rodadas/{rodada_id}/projetos/{projeto_id}/justificativa")
def justificar_projeto(
    rodada_id: int,
    projeto_id: int,
    request: JustificarRequest,
    current_user=Depends(require_diretor_projetos),
    db: Session = Depends(get_db),
):
    try:
        return JustificarProjetoUseCase(db).execute(rodada_id, projeto_id, request, current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.delete("/rodadas/{rodada_id}/projetos/{projeto_id}/justificativa")
def desfazer_justificativa(
    rodada_id: int, projeto_id: int, _=Depends(require_diretor_projetos), db: Session = Depends(get_db)
):
    try:
        return DesfazerJustificativaUseCase(db).execute(rodada_id, projeto_id)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


# ---------------------------------------------------------------- minhas ações
#
# Router à parte, SEM a caixa: o responsável por uma ação costuma ser
# coordenador, que não vê o Health Track. Ele vê a ação dele (problema,
# próxima ação, prazo) e marca como feita. As cores dos pilares não passam
# por aqui.

router_pessoal = APIRouter(
    prefix="/health-track/minhas-acoes", tags=["health track"], dependencies=[Depends(get_current_user)]
)


@router_pessoal.get("")
def minhas_acoes(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ListMinhasAcoesUseCase(db).execute(current_user.id)


@router_pessoal.post("/{acao_id}/concluir")
def concluir_minha_acao(
    acao_id: int, concluida: bool = True, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        return ConcluirMinhaAcaoUseCase(db).execute(acao_id, concluida, current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


# ---------------------------------------------------------------- ações (§15)
#
# Ler: a caixa. Criar, editar, concluir e apagar: quem preenche o Health
# Track do projeto (diretoria de projetos ou gerente da frente).


@router.get("/acoes")
def acoes_abertas(db: Session = Depends(get_db)):
    return ListAcoesAbertasUseCase(db).execute()


@router.get("/projetos/{projeto_id}/acoes")
def acoes_do_projeto(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db, somente_leitura_ok=True)
    return ListAcoesDoProjetoUseCase(db).execute(projeto_id)


@router.post("/projetos/{projeto_id}/acoes", status_code=201)
def criar_acao(
    projeto_id: int, request: AcaoRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    exigir_pode_preencher_health_track(projeto_id, current_user, db)
    try:
        return CriarAcaoUseCase(db).execute(projeto_id, request, current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.put("/projetos/{projeto_id}/acoes/{acao_id}")
def editar_acao(
    projeto_id: int,
    acao_id: int,
    request: AcaoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exigir_pode_preencher_health_track(projeto_id, current_user, db)
    try:
        return EditarAcaoUseCase(db).execute(projeto_id, acao_id, request)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.post("/projetos/{projeto_id}/acoes/{acao_id}/concluir")
def concluir_acao(
    projeto_id: int,
    acao_id: int,
    concluida: bool = True,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exigir_pode_preencher_health_track(projeto_id, current_user, db)
    try:
        return ConcluirAcaoUseCase(db).execute(projeto_id, acao_id, concluida, current_user)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.delete("/projetos/{projeto_id}/acoes/{acao_id}", status_code=204)
def apagar_acao(
    projeto_id: int, acao_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    exigir_pode_preencher_health_track(projeto_id, current_user, db)
    try:
        ApagarAcaoUseCase(db).execute(projeto_id, acao_id)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.get("/evolucao")
def evolucao(db: Session = Depends(get_db)):
    """§16: a carteira rodada a rodada (status geral e cor de cada pilar),
    mais o ponto de hoje."""
    return GetEvolucaoUseCase(db).execute()


@router.get("/pilares")
def listar_pilares(todos: bool = False, db: Session = Depends(get_db)):
    """`?todos=true` inclui os desativados (tela de configuração)."""
    if todos:
        return ListarTodosPilaresUseCase(db).execute()
    return ListarPilaresUseCase(db).execute()


@router.post("/pilares", status_code=201)
def criar_pilar(
    request: PilarRequest, _=Depends(require_diretor_projetos), db: Session = Depends(get_db)
):
    try:
        return CriarPilarUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.put("/pilares/{pilar_id}")
def editar_pilar(
    pilar_id: int,
    request: EditarPilarRequest,
    _=Depends(require_diretor_projetos),
    db: Session = Depends(get_db),
):
    try:
        return EditarPilarUseCase(db).execute(pilar_id, request)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


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


@router.delete("/projetos/{projeto_id}/avaliacoes/ciclos")
def apagar_ciclo(
    projeto_id: int,
    avaliado_em: datetime,
    _=Depends(require_diretor_projetos),
    db: Session = Depends(get_db),
):
    """Apaga UM preenchimento (todas as linhas com esse `avaliado_em`)."""
    try:
        return ApagarCicloUseCase(db).execute(projeto_id, avaliado_em)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)


@router.delete("/tudo")
def zerar(_=Depends(require_diretor_projetos), db: Session = Depends(get_db)):
    """Apaga todas as avaliações, rodadas e ações. Pilares e regra ficam."""
    return ZerarHealthTrackUseCase(db).execute()


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
