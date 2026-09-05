"""Bancas, candidaturas, equipe do projeto e o vínculo banca ↔ frente."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    eh_diretoria_de_projetos,
    exigir_acesso_ao_projeto,
    require_diretor_projetos,
    require_gestao,
    require_pode_aprovar_pedidos,
    require_pode_ver_dashboard_bancas,
    require_lideranca,
    require_pode_definir_cronograma,
    usuario_tem_permissao,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.banca.aprovar_banca import (
    ListarBancasEsperandoAprovacaoUseCase,
    RegistrarAprovacaoBancaRequest,
    RegistrarAprovacaoBancaUseCase,
)
from src.use_cases.banca.create_banca import CreateBancaUseCase, CreateBancaRequest
from src.use_cases.banca.get_banca import GetBancaUseCase, ListBancasUseCase
from src.use_cases.banca.get_banca_detalhes import GetBancaDetalhesUseCase
from src.use_cases.banca.get_historico_bancas import GetHistoricoBancasUseCase
from src.use_cases.banca.get_notas_por_pergunta import GetNotasPorPerguntaUseCase
from src.use_cases.banca.push_alocacao_automatica import PushAlocacaoAutomaticaUseCase
from src.use_cases.banca.excecao_choque import (
    DecidirExcecaoChoqueRequest,
    DecidirExcecaoChoqueUseCase,
    ListarExcecoesChoquePendentesUseCase,
    SolicitarExcecaoChoqueRequest,
    SolicitarExcecaoChoqueUseCase,
)
from src.use_cases.banca.fora_janela import (
    DecidirForaJanelaRequest,
    DecidirForaJanelaUseCase,
    ListarForaJanelaPendentesUseCase,
    SolicitarForaJanelaRequest,
    SolicitarForaJanelaUseCase,
)
from src.use_cases.banca.marcar_banca_escopo import (
    CancelarBancaUseCase,
    MarcarBancaEscopoRequest,
    MarcarBancaEscopoUseCase,
)
from src.use_cases.banca.registrar_descricao_coordenador import (
    RegistrarDescricaoCoordenadorRequest,
    RegistrarDescricaoCoordenadorUseCase,
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
from src.utils.erro_http import erro_de_regra
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(tags=["bancas"], dependencies=[Depends(get_current_user)])


def _exigir_acesso_a_banca(banca_id: int, current_user, db: Session) -> None:
    """§3 nas rotas que agem sobre UMA banca.

    `require_pode_definir_cronograma` só olha a permissão da posição, que não
    é escopo: sem isto, toda coordenadora podia realizar, aprovar ou apagar a
    banca de qualquer projeto — inclusive de um que ela recebe 404 ao tentar
    abrir. E aprovar banca é o que LIBERA a entrega ao cliente (§5.5).

    O caminho é banca → `banca_escopo` → `projeto_escopo` → projeto, e a
    checagem é a mesma `exigir_acesso_ao_projeto` do resto da plataforma (404,
    não 403: quem não enxerga o projeto não deve nem saber que ele existe).

    ⚠ Banca sem vínculo com escopo nenhum é a banca LEGADA, cadastrada antes de
    `banca_escopo` existir — não há projeto a partir do qual decidir. Essas
    continuam valendo só a permissão da posição, senão o legado ficaria
    inadministrável.
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
            request, coordenador_id=current_user.id, eh_diretor_projetos=eh_diretoria_de_projetos(current_user)
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/bancas")
def list_bancas(db: Session = Depends(get_db)):
    return ListBancasUseCase(db).execute()


# ⚠️ Precisa vir ANTES de /bancas/{banca_id}, senão o FastAPI casa
# "esperando-aprovacao" como `banca_id` (int) e devolve 422 — mesma armadilha
# documentada em /formularios/ativo (routers/avaliacoes.py).
@router.get("/bancas/esperando-aprovacao")
def listar_bancas_esperando_aprovacao(current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    """A fila "Esperando aprovação" da aba Bancas — diretoria vê tudo, gerente
    só as bancas com frente dele (§3)."""
    return ListarBancasEsperandoAprovacaoUseCase(db).execute(current_user)


@router.get("/bancas/{banca_id}")
def get_banca(banca_id: int, db: Session = Depends(get_db)):
    result = GetBancaUseCase(db).execute(banca_id)
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result


@router.get("/bancas/{banca_id}/detalhes")
def get_banca_detalhes(
    banca_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    """A ficha da banca com os nomes resolvidos — abre de dentro do
    cronograma do projeto E do "ver mais" da página `/bancas`.

    ⚠ **Só exige login** (2026-09-04, a pedido — quem está NA banca sempre
    foi informação aberta a qualquer um da casa, avaliador ou não). Chegou a
    ter recorte de acesso ao projeto aqui (§3, com exceção de avaliador
    escalado — `exigir_acesso_a_banca_do_projeto`), mas isso quebrava
    exatamente o caso comum: a lista corrida de nomes que a página `/bancas`
    sempre mostrou pra qualquer um (via `contexto.candidaturas` +
    `contexto.usuarios`, sem checagem nenhuma) virava 404 nesta versão
    agrupada só porque a pessoa não tinha OUTRO vínculo com o projeto além
    de estar avaliando — ou nem isso. Essa ficha não é dado sensível do
    projeto (orçamento, cliente, proposta); é só quem está na banca.
    """
    detalhes = GetBancaDetalhesUseCase(db).execute(banca_id)
    if not detalhes:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return detalhes


@router.get("/bancas/{banca_id}/notas-por-pergunta")
def get_notas_por_pergunta(banca_id: int, _=Depends(require_pode_ver_dashboard_bancas), db: Session = Depends(get_db)):
    return GetNotasPorPerguntaUseCase(db).execute(banca_id)


@router.patch("/bancas/{banca_id}")
def update_banca(banca_id: int, request: UpdateBancaRequest, current_user=Depends(require_pode_definir_cronograma), db: Session = Depends(get_db)):
    _exigir_acesso_a_banca(banca_id, current_user, db)
    try:
        result = UpdateBancaUseCase(db).execute(
            banca_id, request, eh_diretor_projetos=eh_diretoria_de_projetos(current_user)
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
def push_alocacao_automatica(_=Depends(require_diretor_projetos), db: Session = Depends(get_db)):
    """Roda na hora a mesma alocação automática por rodízio do agendador
    diário (§8) — para a diretoria disparar manualmente e para teste."""
    return PushAlocacaoAutomaticaUseCase(db).execute()


# ------------------------------------------------------- realização e resultado (F5)
#
# ⚠ 2026-09-04, a pedido: não existe mais "Registrar realização". `data_hora`
# passar sozinho já marca a banca como realizada e dispara a avaliação de
# banca e a de desempenho de finalização (ver
# `use_cases/banca/finalizacao_automatica.py`, rodado pelo agendador). A
# única ação manual que resta é CANCELAR — ver `cancelar_banca` abaixo.


@router.post("/bancas/{banca_id}/cancelar")
def cancelar_banca(banca_id: int, _=Depends(require_gestao), db: Session = Depends(get_db)):
    """⭐ A saída pra "isto não vai acontecer". Gerência e diretoria de
    projetos — tirar uma banca da rotina automática é decisão de gestão do
    calendário, não de condução do projeto (por isso `require_gestao`, e não
    `require_pode_definir_cronograma`, que a coordenação também tem).

    Só antes de `realizado_em`: depois disso a banca já aconteceu, não há o
    que cancelar (ver `CancelarBancaUseCase`)."""
    try:
        result = CancelarBancaUseCase(db).execute(banca_id)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result


@router.patch("/bancas/{banca_id}/descricao-coordenador")
def registrar_descricao_coordenador(
    banca_id: int,
    request: RegistrarDescricaoCoordenadorRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """O relato do coordenador sobre a banca — ele não é avaliador dela."""
    try:
        result = RegistrarDescricaoCoordenadorUseCase(db).execute(banca_id, request, usuario_id=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result


@router.post("/bancas/{banca_id}/aprovacao")
def registrar_aprovacao_banca(
    banca_id: int,
    request: RegistrarAprovacaoBancaRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """🔒 Aprovar ou reprovar a banca (§5.5, §8).

    ⭐ Quem decide é a diretoria de projetos OU o gerente de qualquer frente
    da banca — qualquer um decide sozinho, sem esperar os demais. O papel de
    quem está chamando é resolvido AQUI a partir do `current_user`, não
    recebido no corpo: se viesse do corpo, qualquer um poderia se declarar
    "gerente" e assinar por um cargo que não é seu.

    Não exige acesso prévio ao projeto: a diretoria decide qualquer banca, e o
    gerente só consegue assinar pela própria frente (o use case rejeita quem
    tenta assinar pela frente de outra pessoa).
    """
    try:
        result = RegistrarAprovacaoBancaUseCase(db).execute(banca_id, request, current_user)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result


@router.post("/bancas/excecoes-choque")
def solicitar_excecao_choque(
    request: SolicitarExcecaoChoqueRequest,
    current_user=Depends(require_pode_definir_cronograma),
    db: Session = Depends(get_db),
):
    """⭐ Pedir para marcar a banca num horário já ocupado (§8).

    Quem MARCA a banca pede — por isso `require_pode_definir_cronograma`, o
    mesmo cargo que a marcação exige. Quem decide é a diretoria, na rota abaixo.
    """
    try:
        result = SolicitarExcecaoChoqueUseCase(db).execute(request, solicitado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return result


@router.get("/bancas/excecoes-choque/pendentes")
def listar_excecoes_choque_pendentes(_=Depends(require_pode_aprovar_pedidos), db: Session = Depends(get_db)):
    """A fila da aba Aprovações."""
    return ListarExcecoesChoquePendentesUseCase(db).execute()


@router.patch("/bancas/excecoes-choque/{pedido_id}")
def decidir_excecao_choque(
    pedido_id: int,
    request: DecidirExcecaoChoqueRequest,
    current_user=Depends(require_pode_aprovar_pedidos),
    db: Session = Depends(get_db),
):
    """§8: a exceção de choque é decisão da diretoria — aqui ela é tomada."""
    try:
        result = DecidirExcecaoChoqueUseCase(db).execute(
            pedido_id, request, respondido_por=current_user.id
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return result


@router.post("/bancas/fora-janela")
def solicitar_fora_janela(
    request: SolicitarForaJanelaRequest,
    current_user=Depends(require_pode_definir_cronograma),
    db: Session = Depends(get_db),
):
    """⭐ Pedir para marcar a banca fora da janela do escopo (§13).

    Quem MARCA a banca pede — por isso `require_pode_definir_cronograma`, o
    mesmo cargo que a marcação exige. Quem decide é a diretoria, na rota abaixo.
    """
    try:
        result = SolicitarForaJanelaUseCase(db).execute(request, solicitado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return result


@router.get("/bancas/fora-janela/pendentes")
def listar_fora_janela_pendentes(_=Depends(require_pode_aprovar_pedidos), db: Session = Depends(get_db)):
    """A fila da aba Aprovações."""
    return ListarForaJanelaPendentesUseCase(db).execute()


@router.patch("/bancas/fora-janela/{pedido_id}")
def decidir_fora_janela(
    pedido_id: int,
    request: DecidirForaJanelaRequest,
    current_user=Depends(require_pode_aprovar_pedidos),
    db: Session = Depends(get_db),
):
    """§13: marcar banca fora da janela é decisão da diretoria — aqui ela é tomada.

    ⚠ `erro_de_regra`, e não `detail=str(e)` como as rotas vizinhas: a recusa
    por choque de horário (§8) carrega `codigo`, e é por ele que a fila oferece
    o "autorizar o choque também". Achatar a exceção em texto aqui apagaria o
    código no caminho, e a tela voltaria a ser um beco sem saída.
    """
    try:
        result = DecidirForaJanelaUseCase(db).execute(
            pedido_id, request, respondido_por=current_user.id
        )
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)
    if not result:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return result


# ⚠ **Rota removida: `PATCH /bancas/{banca_id}/excecao-choque`.**
#
# Ela gravava `excecao_choque_por` na banca que JÁ ocupava o horário, e
# `_checar_choque` pulava toda banca com essa flag — ou seja, uma liberação
# pontual transformava aquele horário em passe livre para QUALQUER banca
# futura. Era o buraco que o redesenho do §8 veio fechar, e mantê-la viva
# significava manter uma porta para reabri-lo.
#
# Nunca teve chamador na interface. O caminho agora é o par (escopo, horário):
# `POST /bancas/excecoes-choque` pede, `PATCH /bancas/excecoes-choque/{id}`
# decide. A flag antiga continua sendo respeitada na leitura para não invalidar
# as exceções já concedidas no banco — o que deixou de existir é como criar
# novas.


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
            eh_diretor_projetos=eh_diretoria_de_projetos(current_user),
            current_user=current_user,
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
    _=Depends(require_pode_ver_dashboard_bancas),
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
    if alvo != current_user.id and not eh_diretoria_de_projetos(current_user):
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
