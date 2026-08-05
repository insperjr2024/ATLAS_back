"""Avaliação de Desempenho — a rodada periódica/de finalização de consultores
e coordenadores. Não confundir com `avaliacoes.py` (feedback de banca)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    require_pode_definir_formulario_desempenho,
    require_pode_gerenciar_desempenho,
    require_self,
    require_self_mentor_ou_gestao,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.desempenho_avaliacao.create_avaliacao import (
    CreateDesempenhoAvaliacaoRequest,
    CreateDesempenhoAvaliacaoUseCase,
)
from src.use_cases.desempenho_avaliacao.delete_avaliacao import DeleteDesempenhoAvaliacaoUseCase
from src.use_cases.desempenho_avaliacao.finalizar import FinalizarDesempenhoRequest, FinalizarDesempenhoUseCase
from src.use_cases.desempenho_avaliacao.get_avaliacao import (
    GetDesempenhoAvaliacaoUseCase,
    ListDesempenhoAvaliacoesUseCase,
)
from src.use_cases.desempenho_avaliacao.get_fila import GetFilaUsuarioUseCase
from src.use_cases.desempenho_avaliacao.get_relatorio import GetRelatorioDesempenhoUseCase
from src.use_cases.desempenho_formulario.get_formulario import GetDesempenhoFormularioUseCase
from src.use_cases.desempenho_formulario.update_formulario import (
    UpdateDesempenhoFormularioRequest,
    UpdateDesempenhoFormularioUseCase,
)
from src.use_cases.desempenho_lote.abrir_fechar_lote import AbrirLoteUseCase, FecharLoteUseCase, SeguirDatasLoteUseCase
from src.use_cases.desempenho_lote.create_lote import CreateDesempenhoLoteRequest, CreateDesempenhoLoteUseCase
from src.use_cases.desempenho_lote.delete_lote import DeleteDesempenhoLoteUseCase
from src.use_cases.desempenho_lote.get_lote import ListDesempenhoLotesUseCase
from src.use_cases.desempenho_lote.get_pendencias import GetPendenciasLoteUseCase
from src.use_cases.desempenho_lote.update_lote import UpdateDesempenhoLoteRequest, UpdateDesempenhoLoteUseCase
from src.use_cases.desempenho_mentoria.create_mentoria import CreateMentoriaRequest, CreateMentoriaUseCase
from src.use_cases.desempenho_mentoria.delete_mentoria import DeleteMentoriaUseCase
from src.use_cases.desempenho_mentoria.get_mentoria import GetMentoradosDeUseCase, ListMentoriasUseCase
from src.utils.exceptions import RegraDeNegocioError, ResourceInUseError

router = APIRouter(tags=["avaliação de desempenho"], dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------- lotes

@router.post("/desempenho/lotes")
def create_lote(request: CreateDesempenhoLoteRequest, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    return CreateDesempenhoLoteUseCase(db).execute(request)


@router.get("/desempenho/lotes")
def list_lotes(abertos: bool = True, db: Session = Depends(get_db)):
    return ListDesempenhoLotesUseCase(db).execute(abertos)


@router.put("/desempenho/lotes/{lote_id}")
def update_lote(lote_id: int, request: UpdateDesempenhoLoteRequest, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    result = UpdateDesempenhoLoteUseCase(db).execute(lote_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return result


@router.delete("/desempenho/lotes/{lote_id}", status_code=204)
def delete_lote(lote_id: int, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    try:
        deleted = DeleteDesempenhoLoteUseCase(db).execute(lote_id)
    except ResourceInUseError:
        raise HTTPException(
            status_code=409,
            detail="Não é possível excluir: este lote já tem avaliações ou finalizações registradas. Feche-o em vez de excluir.",
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return None


@router.post("/desempenho/lotes/{lote_id}/abrir")
def abrir_lote(lote_id: int, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    result = AbrirLoteUseCase(db).execute(lote_id)
    if not result:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return result


@router.post("/desempenho/lotes/{lote_id}/fechar")
def fechar_lote(lote_id: int, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    result = FecharLoteUseCase(db).execute(lote_id)
    if not result:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return result


@router.post("/desempenho/lotes/{lote_id}/seguir-datas")
def seguir_datas_lote(lote_id: int, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    result = SeguirDatasLoteUseCase(db).execute(lote_id)
    if not result:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return result


@router.get("/desempenho/lotes/{lote_id}/pendencias")
def get_pendencias(lote_id: int, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    result = GetPendenciasLoteUseCase(db).execute(lote_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return result


# ---------------------------------------------------------------- formulários

@router.get("/desempenho/formularios/{tipo}/{papel}")
def get_formulario(tipo: str, papel: str, db: Session = Depends(get_db)):
    result = GetDesempenhoFormularioUseCase(db).execute(tipo, papel)
    if not result:
        raise HTTPException(status_code=404, detail="Formulário não encontrado")
    return result


@router.put("/desempenho/formularios/{tipo}/{papel}")
def update_formulario(
    tipo: str,
    papel: str,
    request: UpdateDesempenhoFormularioRequest,
    _=Depends(require_pode_definir_formulario_desempenho),
    db: Session = Depends(get_db),
):
    result = UpdateDesempenhoFormularioUseCase(db).execute(tipo, papel, request)
    if not result:
        raise HTTPException(status_code=404, detail="Formulário não encontrado")
    return result


# ---------------------------------------------------------------- avaliações

@router.post("/desempenho/avaliacoes")
def create_avaliacao(
    request: CreateDesempenhoAvaliacaoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return CreateDesempenhoAvaliacaoUseCase(db).execute(request, avaliador_id=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/desempenho/avaliacoes")
def list_avaliacoes(_=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    return ListDesempenhoAvaliacoesUseCase(db).execute()


@router.get("/desempenho/avaliacoes/{avaliacao_id}")
def get_avaliacao(avaliacao_id: int, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    result = GetDesempenhoAvaliacaoUseCase(db).execute(avaliacao_id)
    if not result:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return result


@router.delete("/desempenho/avaliacoes/{avaliacao_id}", status_code=204)
def delete_avaliacao(avaliacao_id: int, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    deleted = DeleteDesempenhoAvaliacaoUseCase(db).execute(avaliacao_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return None


# ---------------------------------------------------------------- mentorias

@router.post("/desempenho/mentorias")
def create_mentoria(request: CreateMentoriaRequest, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    try:
        return CreateMentoriaUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/desempenho/mentorias/{mentoria_id}", status_code=204)
def delete_mentoria(mentoria_id: int, _=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    deleted = DeleteMentoriaUseCase(db).execute(mentoria_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mentoria não encontrada")
    return None


@router.get("/desempenho/mentorias")
def list_mentorias(_=Depends(require_pode_gerenciar_desempenho), db: Session = Depends(get_db)):
    return ListMentoriasUseCase(db).execute()


# ---------------------------------------------------------------- usuário-escopado

@router.get("/usuarios/{usuario_id}/desempenho/fila")
def get_minha_fila(usuario_id: int, _=Depends(require_self), db: Session = Depends(get_db)):
    return GetFilaUsuarioUseCase(db).execute(usuario_id)


@router.post("/usuarios/{usuario_id}/desempenho/finalizar")
def finalizar(
    usuario_id: int,
    request: FinalizarDesempenhoRequest,
    _=Depends(require_self),
    db: Session = Depends(get_db),
):
    return FinalizarDesempenhoUseCase(db).execute(usuario_id, request.lote_id)


@router.get("/usuarios/{usuario_id}/desempenho/relatorio")
def get_relatorio(
    usuario_id: int,
    lote_id: Optional[int] = None,
    tipo: Optional[str] = None,
    _=Depends(require_self_mentor_ou_gestao),
    db: Session = Depends(get_db),
):
    return GetRelatorioDesempenhoUseCase(db).execute(usuario_id, lote_id, tipo)


@router.get("/usuarios/{usuario_id}/desempenho/mentorados")
def get_meus_mentorados(usuario_id: int, _=Depends(require_self), db: Session = Depends(get_db)):
    return GetMentoradosDeUseCase(db).execute(usuario_id)
