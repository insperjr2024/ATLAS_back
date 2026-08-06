"""Bancas, candidaturas, equipe do projeto e o vínculo banca ↔ frente."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    exigir_acesso_ao_projeto,
    require_diretor,
    require_lideranca,
    require_pode_definir_cronograma,
    usuario_tem_permissao,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.banca.create_banca import CreateBancaUseCase, CreateBancaRequest
from src.use_cases.banca.get_banca import GetBancaUseCase, ListBancasUseCase
from src.use_cases.banca.get_historico_bancas import GetHistoricoBancasUseCase
from src.use_cases.banca.get_notas_por_pergunta import GetNotasPorPerguntaUseCase
from src.use_cases.banca.push_alocacao_automatica import PushAlocacaoAutomaticaUseCase
from src.use_cases.banca.marcar_banca_escopo import (
    LiberarExcecaoChoqueRequest,
    LiberarExcecaoChoqueUseCase,
    MarcarBancaEscopoRequest,
    MarcarBancaEscopoUseCase,
    RegistrarRealizacaoBancaUseCase,
    RegistrarRealizacaoRequest,
    RegistrarResultadoBancaUseCase,
    RegistrarResultadoRequest,
)
from src.use_cases.banca.update_banca import UpdateBancaUseCase, UpdateBancaRequest, DeleteBancaUseCase
from src.use_cases.banca_frente.create_banca_frente import CreateBancaFrenteUseCase, CreateBancaFrenteRequest
from src.use_cases.banca_frente.get_banca_frente import GetBancaFrenteUseCase, ListBancasFrentesUseCase
from src.use_cases.banca_frente.update_banca_frente import (
    UpdateBancaFrenteUseCase,
    UpdateBancaFrenteRequest,
    DeleteBancaFrenteUseCase,
)
from src.use_cases.candidatura.create_candidatura import CreateCandidaturaUseCase, CreateCandidaturaRequest
from src.use_cases.candidatura.get_candidatura import GetCandidaturaUseCase, ListCandidaturasUseCase
from src.use_cases.candidatura.update_candidatura import (
    UpdateCandidaturaUseCase,
    UpdateCandidaturaRequest,
    DeleteCandidaturaUseCase,
)
from src.use_cases.equipe_projeto.create_equipe_projeto import CreateEquipeProjetoUseCase, CreateEquipeProjetoRequest
from src.use_cases.equipe_projeto.get_equipe_projeto import GetEquipeProjetoUseCase, ListEquipesProjetoUseCase
from src.use_cases.equipe_projeto.update_equipe_projeto import (
    UpdateEquipeProjetoUseCase,
    UpdateEquipeProjetoRequest,
    DeleteEquipeProjetoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(tags=["bancas"], dependencies=[Depends(get_current_user)])


def _exigir_acesso_a_banca(banca_id: int, current_user, db: Session) -> None:
    """§3 nas rotas que agem sobre UMA banca.

    `require_pode_definir_cronograma` só olha o cargo, e cargo não é escopo:
    sem isto, toda coordenadora podia realizar, aprovar ou apagar a banca de
    qualquer projeto — inclusive de um que ela recebe 404 ao tentar abrir. E
    aprovar banca é o que LIBERA a entrega ao cliente (§5.5).

    O caminho é banca → `banca_escopo` → `projeto_escopo` → projeto, e a
    checagem é a mesma `exigir_acesso_ao_projeto` do resto da plataforma (404,
    não 403: quem não enxerga o projeto não deve nem saber que ele existe).

    ⚠ Banca sem vínculo com escopo nenhum é a banca LEGADA, cadastrada antes de
    `banca_escopo` existir — não há projeto a partir do qual decidir. Essas
    continuam valendo só o cargo, senão o legado ficaria inadministrável.
    """
    from src.repositories.banca_escopo_repository import BancaEscopoRepository
    from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository

    escopo_ids = BancaEscopoRepository(db).get_escopo_ids(banca_id)
    projeto_escopo_repository = ProjetoEscopoRepository(db)
    for escopo_id in escopo_ids:
        escopo = projeto_escopo_repository.get_by_id(escopo_id)
        if escopo:
            exigir_acesso_ao_projeto(escopo.projeto_id, current_user, db)


# ---------------------------------------------------------------- bancas

@router.post("/bancas")
def create_banca(request: CreateBancaRequest, current_user=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    try:
        return CreateBancaUseCase(db).execute(
            request, coordenador_id=current_user.id, eh_diretor=current_user.posicao == "diretor"
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/bancas")
def list_bancas(db: Session = Depends(get_db)):
    return ListBancasUseCase(db).execute()


@router.get("/bancas/{banca_id}")
def get_banca(banca_id: int, db: Session = Depends(get_db)):
    result = GetBancaUseCase(db).execute(banca_id)
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result


@router.get("/bancas/{banca_id}/notas-por-pergunta")
def get_notas_por_pergunta(banca_id: int, _=Depends(require_diretor), db: Session = Depends(get_db)):
    return GetNotasPorPerguntaUseCase(db).execute(banca_id)


@router.patch("/bancas/{banca_id}")
def update_banca(banca_id: int, request: UpdateBancaRequest, current_user=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    _exigir_acesso_a_banca(banca_id, current_user, db)
    try:
        result = UpdateBancaUseCase(db).execute(
            banca_id, request, eh_diretor=current_user.posicao == "diretor"
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result


@router.delete("/bancas/{banca_id}", status_code=204)
def delete_banca(banca_id: int, current_user=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    _exigir_acesso_a_banca(banca_id, current_user, db)
    deleted = DeleteBancaUseCase(db).execute(banca_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return None


@router.post("/bancas/push-alocacao")
def push_alocacao_automatica(_=Depends(require_diretor), db: Session = Depends(get_db)):
    """Roda na hora a mesma alocação automática por rodízio do agendador
    diário (§8) — para a diretoria disparar manualmente e para teste."""
    return PushAlocacaoAutomaticaUseCase(db).execute()


# ------------------------------------------------------- realização e resultado (F5)
#
# ⚠ Duas dimensões de permissão convivem aqui, e confundi-las gera 403
# inexplicável: `cargo` (pode_agendar_banca) manda nas ações do módulo de
# bancas; `posicao` manda no resto. Marcar a banca PELO CRONOGRAMA é ação de
# posição — é a coordenadora cravando o cronograma do projeto dela, e ela não
# precisa da flag do núcleo para isso.


@router.post("/bancas/{banca_id}/realizar")
def realizar_banca(banca_id: int, request: RegistrarRealizacaoRequest, current_user=Depends(get_current_user), _=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    """⭐ Marca que a banca ACONTECEU. Sem isto ela fica `atrasada` para sempre.

    Exige o mínimo de gente alocada; `forcar` passa por cima, e só para a
    diretoria — é ela que libera exceção de composição (§8).
    """
    try:
        result = RegistrarRealizacaoBancaUseCase(db).execute(
            banca_id, request, eh_diretor=current_user.posicao == "diretor"
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result


@router.patch("/bancas/{banca_id}/resultado")
def registrar_resultado(banca_id: int, request: RegistrarResultadoRequest, current_user=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    """🔒 É o resultado que libera a entrega ao cliente (§5.5, §8)."""
    _exigir_acesso_a_banca(banca_id, current_user, db)
    try:
        result = RegistrarResultadoBancaUseCase(db).execute(banca_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result


@router.patch("/bancas/{banca_id}/excecao-choque")
def liberar_excecao_choque(banca_id: int, request: LiberarExcecaoChoqueRequest, current_user=Depends(require_diretor), db: Session = Depends(get_db)):
    """§8: a exceção de choque de horário só é liberada pela diretoria."""
    try:
        result = LiberarExcecaoChoqueUseCase(db).execute(banca_id, request, liberado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result


@router.put("/escopos-projeto/{escopo_id}/banca")
def marcar_banca_do_escopo(escopo_id: int, request: MarcarBancaEscopoRequest, current_user=Depends(require_lideranca), db: Session = Depends(get_db)):
    """Marcar a banca do escopo — "uma data só" (§8).

    Escreve na MESMA linha de `banca` que a tela de Bancas lê. Não há espelho
    nem rotina de sincronização, de propósito.

    `escopo_ids` no corpo diz quais escopos do projeto esta banca cobre (o da
    URL entra sempre). Omitido, os vínculos atuais ficam como estão.
    """
    from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository

    escopo = ProjetoEscopoRepository(db).get_by_id(escopo_id)
    if not escopo:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    exigir_acesso_ao_projeto(escopo.projeto_id, current_user, db)

    try:
        result = MarcarBancaEscopoUseCase(db).execute(
            escopo_id,
            request,
            eh_diretor=current_user.posicao == "diretor",
            registrado_por=current_user.id,
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return result


@router.get("/historico-bancas")
def get_historico_bancas(
    consultor_id: Optional[int] = None,
    coordenador_id: Optional[int] = None,
    escopo_id: Optional[int] = None,
    semestre_id: Optional[int] = None,
    _=Depends(require_diretor),
    db: Session = Depends(get_db),
):
    return GetHistoricoBancasUseCase(db).execute(consultor_id, coordenador_id, escopo_id, semestre_id)


# ---------------------------------------------------------------- candidaturas

@router.post("/candidaturas")
def create_candidatura(request: CreateCandidaturaRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Inscrição própria — ou alocação de outra pessoa, se for a diretoria.

    Escalar alguém mexe na agenda dele sem que tenha pedido, então essa porta
    é da diretoria (§8: é ela quem faz a alocação por push).
    """
    alvo = request.usuario_id or current_user.id
    if alvo != current_user.id and current_user.posicao != "diretor":
        raise HTTPException(
            status_code=403,
            detail="Apenas o Diretor de Projetos pode alocar outra pessoa numa banca",
        )
    try:
        return CreateCandidaturaUseCase(db).execute(request, usuario_id=alvo)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/candidaturas")
def list_candidaturas(db: Session = Depends(get_db)):
    return ListCandidaturasUseCase(db).execute()


@router.get("/candidaturas/{candidatura_id}")
def get_candidatura(candidatura_id: int, db: Session = Depends(get_db)):
    result = GetCandidaturaUseCase(db).execute(candidatura_id)
    if not result:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada")
    return result


@router.patch("/candidaturas/{candidatura_id}")
def update_candidatura(candidatura_id: int, request: UpdateCandidaturaRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    existente = GetCandidaturaUseCase(db).execute(candidatura_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada")
    if existente["usuario_id"] != current_user.id and not usuario_tem_permissao(current_user, db, "pode_gerir_membros"):
        raise HTTPException(status_code=403, detail="Você só pode editar suas próprias candidaturas")
    result = UpdateCandidaturaUseCase(db).execute(candidatura_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada")
    return result


@router.delete("/candidaturas/{candidatura_id}", status_code=204)
def delete_candidatura(candidatura_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    existente = GetCandidaturaUseCase(db).execute(candidatura_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada")
    if existente["usuario_id"] != current_user.id and not usuario_tem_permissao(current_user, db, "pode_gerir_membros"):
        raise HTTPException(status_code=403, detail="Você só pode remover suas próprias candidaturas")
    try:
        deleted = DeleteCandidaturaUseCase(db).execute(candidatura_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada")
    return None


# ---------------------------------------------------------------- equipe do projeto
# ⚠️ Legado: substituída por projeto_membro na Prioridade 1. Mantida enquanto
# as bancas já cadastradas apontarem para ela.

@router.post("/equipes-projeto")
def create_equipe_projeto(request: CreateEquipeProjetoRequest, _=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    return CreateEquipeProjetoUseCase(db).execute(request)


@router.get("/equipes-projeto")
def list_equipes_projeto(db: Session = Depends(get_db)):
    return ListEquipesProjetoUseCase(db).execute()


@router.get("/equipes-projeto/{equipe_id}")
def get_equipe_projeto(equipe_id: int, db: Session = Depends(get_db)):
    result = GetEquipeProjetoUseCase(db).execute(equipe_id)
    if not result:
        raise HTTPException(status_code=404, detail="Registro de equipe não encontrado")
    return result


@router.patch("/equipes-projeto/{equipe_id}")
def update_equipe_projeto(equipe_id: int, request: UpdateEquipeProjetoRequest, _=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    result = UpdateEquipeProjetoUseCase(db).execute(equipe_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Registro de equipe não encontrado")
    return result


@router.delete("/equipes-projeto/{equipe_id}", status_code=204)
def delete_equipe_projeto(equipe_id: int, _=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    deleted = DeleteEquipeProjetoUseCase(db).execute(equipe_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro de equipe não encontrado")
    return None


# ---------------------------------------------------------------- banca ↔ frente

@router.post("/bancas-frentes")
def create_banca_frente(request: CreateBancaFrenteRequest, _=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    return CreateBancaFrenteUseCase(db).execute(request)


@router.get("/bancas-frentes")
def list_bancas_frentes(db: Session = Depends(get_db)):
    return ListBancasFrentesUseCase(db).execute()


@router.get("/bancas-frentes/{banca_frente_id}")
def get_banca_frente(banca_frente_id: int, db: Session = Depends(get_db)):
    result = GetBancaFrenteUseCase(db).execute(banca_frente_id)
    if not result:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return result


@router.patch("/bancas-frentes/{banca_frente_id}")
def update_banca_frente(banca_frente_id: int, request: UpdateBancaFrenteRequest, _=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    result = UpdateBancaFrenteUseCase(db).execute(banca_frente_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return result


@router.delete("/bancas-frentes/{banca_frente_id}", status_code=204)
def delete_banca_frente(banca_frente_id: int, _=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    deleted = DeleteBancaFrenteUseCase(db).execute(banca_frente_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return None
