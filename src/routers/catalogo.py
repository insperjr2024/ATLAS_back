"""Cargos, escopos, frentes, semestres e configuração — a base que a
diretoria mantém e que todo o resto referencia."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import require_pode_administrar_configuracoes
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.dia_nao_letivo.create_dia_nao_letivo import (
    CreateDiasNaoLetivosUseCase,
    CreateDiasNaoLetivosRequest,
)
from src.use_cases.dia_nao_letivo.delete_dia_nao_letivo import (
    DeleteDiaNaoLetivoUseCase,
    DeleteDiasNaoLetivosDoSemestreUseCase,
)
from src.use_cases.dia_nao_letivo.get_dia_nao_letivo import (
    GetDiasNaoUteisUseCase,
    ListDiasNaoLetivosUseCase,
)
from src.use_cases.dia_nao_letivo.ler_calendario_pdf import LerCalendarioPdfUseCase
from src.use_cases.calendario.get_eventos import GetEventosCalendarioUseCase
from src.use_cases.semestre.get_semestre import GetSemestreAtivoUseCase
from src.utils.exceptions import RegraDeNegocioError
from src.use_cases.posicao_permissao.get_posicao_permissao import ListPosicaoPermissoesUseCase
from src.use_cases.posicao_permissao.update_posicao_permissao import (
    UpdatePosicaoPermissaoUseCase,
    UpdatePosicaoPermissaoRequest,
)
from src.use_cases.configuracao.get_configuracao import GetConfiguracaoUseCase
from src.use_cases.configuracao.update_configuracao import UpdateConfiguracaoUseCase, UpdateConfiguracaoRequest
from src.use_cases.situacao_carga.gerenciar_situacoes import (
    AtualizarSituacaoRequest,
    SituacaoCargaUseCase,
)
from src.use_cases.escopo.create_escopo import CreateEscopoUseCase, CreateEscopoRequest
from src.use_cases.escopo.get_escopo import GetEscopoUseCase, ListEscoposUseCase
from src.use_cases.escopo.update_escopo import UpdateEscopoUseCase, UpdateEscopoRequest, DeleteEscopoUseCase
from src.use_cases.frente.create_frente import CreateFrenteUseCase, CreateFrenteRequest
from src.use_cases.frente.get_frente import GetFrenteUseCase, ListFrentesUseCase
from src.use_cases.frente.update_frente import UpdateFrenteUseCase, UpdateFrenteRequest, DeleteFrenteUseCase
from src.use_cases.semestre.create_semestre import CreateSemestreUseCase, CreateSemestreRequest
from src.use_cases.semestre.get_semestre import GetSemestreUseCase, ListSemestresUseCase
from src.use_cases.semestre.update_semestre import UpdateSemestreUseCase, UpdateSemestreRequest, DeleteSemestreUseCase
from src.utils.exceptions import ResourceInUseError

router = APIRouter(tags=["catálogo"], dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------- permissões por posição

@router.get("/posicoes-permissoes")
def list_posicoes_permissoes(db: Session = Depends(get_db)):
    return ListPosicaoPermissoesUseCase(db).execute()


@router.patch("/posicoes-permissoes/{posicao}")
def update_posicao_permissao(
    posicao: str,
    request: UpdatePosicaoPermissaoRequest,
    _=Depends(require_pode_administrar_configuracoes),
    db: Session = Depends(get_db),
):
    result = UpdatePosicaoPermissaoUseCase(db).execute(posicao, request)
    if not result:
        raise HTTPException(status_code=404, detail="Posição não encontrada")
    return result


# ---------------------------------------------------------------- escopos

@router.post("/escopos")
def create_escopo(request: CreateEscopoRequest, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    return CreateEscopoUseCase(db).execute(request)


@router.get("/escopos")
def list_escopos(
    frente_id: Optional[int] = None,
    apenas_ativos: bool = False,
    db: Session = Depends(get_db),
):
    return ListEscoposUseCase(db).execute(frente_id=frente_id, apenas_ativos=apenas_ativos)


@router.get("/escopos/{escopo_id}")
def get_escopo(escopo_id: int, db: Session = Depends(get_db)):
    result = GetEscopoUseCase(db).execute(escopo_id)
    if not result:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return result


@router.patch("/escopos/{escopo_id}")
def update_escopo(escopo_id: int, request: UpdateEscopoRequest, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    result = UpdateEscopoUseCase(db).execute(escopo_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return result


@router.delete("/escopos/{escopo_id}", status_code=204)
def delete_escopo(escopo_id: int, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    try:
        deleted = DeleteEscopoUseCase(db).execute(escopo_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a este escopo")
    if not deleted:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return None


# ---------------------------------------------------------------- frentes

@router.post("/frentes")
def create_frente(request: CreateFrenteRequest, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    return CreateFrenteUseCase(db).execute(request)


@router.get("/frentes")
def list_frentes(apenas_ativas: bool = False, db: Session = Depends(get_db)):
    return ListFrentesUseCase(db).execute(apenas_ativas=apenas_ativas)


@router.get("/frentes/{frente_id}")
def get_frente(frente_id: int, db: Session = Depends(get_db)):
    result = GetFrenteUseCase(db).execute(frente_id)
    if not result:
        raise HTTPException(status_code=404, detail="Frente não encontrada")
    return result


@router.patch("/frentes/{frente_id}")
def update_frente(frente_id: int, request: UpdateFrenteRequest, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    result = UpdateFrenteUseCase(db).execute(frente_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Frente não encontrada")
    return result


@router.delete("/frentes/{frente_id}", status_code=204)
def delete_frente(frente_id: int, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    try:
        deleted = DeleteFrenteUseCase(db).execute(frente_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a esta frente")
    if not deleted:
        raise HTTPException(status_code=404, detail="Frente não encontrada")
    return None


# ---------------------------------------------------------------- semestres

@router.post("/semestres")
def create_semestre(request: CreateSemestreRequest, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    try:
        return CreateSemestreUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/semestres")
def list_semestres(db: Session = Depends(get_db)):
    return ListSemestresUseCase(db).execute()


# ⚠️ Precisa vir antes de /semestres/{semestre_id}, senão "ativo" casa como path param.
@router.get("/semestres/ativo")
def get_semestre_ativo(db: Session = Depends(get_db)):
    result = GetSemestreAtivoUseCase(db).execute()
    if not result:
        raise HTTPException(status_code=404, detail="Nenhuma gestão ativa")
    return result


@router.get("/semestres/{semestre_id}")
def get_semestre(semestre_id: int, db: Session = Depends(get_db)):
    result = GetSemestreUseCase(db).execute(semestre_id)
    if not result:
        raise HTTPException(status_code=404, detail="Semestre não encontrado")
    return result


@router.patch("/semestres/{semestre_id}")
def update_semestre(semestre_id: int, request: UpdateSemestreRequest, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    try:
        result = UpdateSemestreUseCase(db).execute(semestre_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Semestre não encontrado")
    return result


@router.delete("/semestres/{semestre_id}", status_code=204)
def delete_semestre(semestre_id: int, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    try:
        deleted = DeleteSemestreUseCase(db).execute(semestre_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a este semestre")
    if not deleted:
        raise HTTPException(status_code=404, detail="Semestre não encontrado")
    return None


# ---------------------------------------------------------------- calendário do Insper
# 📐 É esta carga que define o dia útil. Sem ela nada da contagem do §5.4 existe.

@router.post("/semestres/{semestre_id}/dias-nao-letivos")
def create_dias_nao_letivos(
    semestre_id: int,
    request: CreateDiasNaoLetivosRequest,
    _=Depends(require_pode_administrar_configuracoes),
    db: Session = Depends(get_db),
):
    try:
        return CreateDiasNaoLetivosUseCase(db).execute(semestre_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/semestres/{semestre_id}/dias-nao-letivos")
def list_dias_nao_letivos(
    semestre_id: int,
    frente_id: Optional[int] = Query(None, description="Calendário base desta frente"),
    apenas_da_frente: bool = Query(False, description="Corta os dias globais da resposta"),
    db: Session = Depends(get_db),
):
    return ListDiasNaoLetivosUseCase(db).execute(semestre_id, frente_id, apenas_da_frente)


@router.post("/semestres/{semestre_id}/dias-nao-letivos/ler-pdf")
async def ler_calendario_pdf(
    semestre_id: int,
    arquivo: UploadFile = File(..., description="Calendário acadêmico do Insper em PDF"),
    frente_id: Optional[int] = Query(None),
    _=Depends(require_pode_administrar_configuracoes),
    db: Session = Depends(get_db),
):
    """Lê o PDF e DEVOLVE o que encontrou — não grava nada.

    A gravação é um POST separado, depois de a diretoria conferir na tela. A
    leitura é posicional e pode errar se o Insper mudar o layout; salvar direto
    contaminaria o cálculo de dias úteis de todos os projetos sem ninguém ver.
    """
    if not (arquivo.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Envie o calendário em PDF")
    try:
        return LerCalendarioPdfUseCase(db).execute(semestre_id, arquivo.file, frente_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/semestres/{semestre_id}/dias-nao-letivos", status_code=204)
def delete_dias_nao_letivos_do_semestre(semestre_id: int, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    DeleteDiasNaoLetivosDoSemestreUseCase(db).execute(semestre_id)
    return None


@router.delete("/dias-nao-letivos/{dia_id}", status_code=204)
def delete_dia_nao_letivo(dia_id: int, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    deleted = DeleteDiaNaoLetivoUseCase(db).execute(dia_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dia não letivo não encontrado")
    return None


@router.get("/calendario/eventos")
def get_eventos_calendario(
    inicio: date,
    fim: date,
    tipos: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """O calendário geral do §6.5 — bancas + kickoffs + reuniões + entregas.

    🔓 **Sem recorte de visão, de propósito**: o §6.5 diz "acessível a todos".
    É a única consulta de projeto do sistema assim — não "consertar".
    """
    lista = [t.strip() for t in tipos.split(",")] if tipos else None
    return GetEventosCalendarioUseCase(db).execute(inicio, fim, lista)


@router.get("/calendario/dias-nao-uteis")
def get_dias_nao_uteis(
    inicio: date = Query(..., description="Primeiro dia do intervalo"),
    fim: date = Query(..., description="Último dia do intervalo"),
    db: Session = Depends(get_db),
):
    """Os dias que o cronograma pinta de cinza: fim de semana + calendário do Insper."""
    if fim < inicio:
        raise HTTPException(status_code=422, detail="O fim do intervalo não pode ser anterior ao início")
    return GetDiasNaoUteisUseCase(db).execute(inicio, fim)


# ---------------------------------------------------------------- configuração

@router.get("/configuracao")
def get_configuracao(db: Session = Depends(get_db)):
    return GetConfiguracaoUseCase(db).execute()


@router.patch("/configuracao")
def update_configuracao(request: UpdateConfiguracaoRequest, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    return UpdateConfiguracaoUseCase(db).execute(request)


# ------------------------------------------------------- situações de carga

@router.get("/situacoes-carga")
def listar_situacoes_carga(db: Session = Depends(get_db)):
    """A escala de carga por papel (§7.3). Leitura livre — a aba de Alocação
    precisa dela para nomear a situação de cada pessoa."""
    return SituacaoCargaUseCase(db).listar()


@router.patch("/situacoes-carga/{situacao_id}")
def atualizar_situacao_carga(situacao_id: int, request: AtualizarSituacaoRequest, _=Depends(require_pode_administrar_configuracoes), db: Session = Depends(get_db)):
    try:
        resultado = SituacaoCargaUseCase(db).atualizar(situacao_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not resultado:
        raise HTTPException(status_code=404, detail="Situação não encontrada")
    return resultado
