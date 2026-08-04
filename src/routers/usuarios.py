"""Usuários, o vínculo N:N com frentes e os indicadores pessoais."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    require_pode_gerenciar_cargos,
    require_self_or_admin,
    usuario_tem_permissao,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.banca.get_bancas_para_avaliar import GetBancasParaAvaliarUseCase
from src.use_cases.usuario.get_desempenho import GetDesempenhoUseCase
from src.use_cases.usuario.get_usuario import GetUsuarioUseCase, ListUsuariosUseCase
from src.use_cases.usuario.update_usuario import UpdateUsuarioUseCase, UpdateUsuarioRequest, DeleteUsuarioUseCase
from src.use_cases.usuario_frente.create_usuario_frente import CreateUsuarioFrenteUseCase, CreateUsuarioFrenteRequest
from src.use_cases.usuario_frente.get_usuario_frente import GetUsuarioFrenteUseCase, ListUsuariosFrentesUseCase
from src.use_cases.usuario_frente.update_usuario_frente import DeleteUsuarioFrenteUseCase
from src.utils.exceptions import ResourceInUseError

router = APIRouter(tags=["usuários"], dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------- usuários

@router.get("/usuarios")
def list_usuarios(
    posicao: Optional[str] = None,
    apenas_ativos: bool = False,
    db: Session = Depends(get_db),
):
    return ListUsuariosUseCase(db).execute(posicao=posicao, apenas_ativos=apenas_ativos)


@router.get("/usuarios/{usuario_id}")
def get_usuario(usuario_id: int, db: Session = Depends(get_db)):
    result = GetUsuarioUseCase(db).execute(usuario_id)
    if not result:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return result


@router.patch("/usuarios/{usuario_id}")
def update_usuario(
    usuario_id: int,
    request: UpdateUsuarioRequest,
    current_user=Depends(require_pode_gerenciar_cargos),
    db: Session = Depends(get_db),
):
    result = UpdateUsuarioUseCase(db).execute(usuario_id, request, alterado_por=current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return result


@router.delete("/usuarios/{usuario_id}", status_code=204)
def delete_usuario(usuario_id: int, _=Depends(require_pode_gerenciar_cargos), db: Session = Depends(get_db)):
    try:
        deleted = DeleteUsuarioUseCase(db).execute(usuario_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a este usuário")
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return None


@router.get("/usuarios/{usuario_id}/bancas-para-avaliar")
def get_bancas_para_avaliar(usuario_id: int, current_user=Depends(require_self_or_admin), db: Session = Depends(get_db)):
    return GetBancasParaAvaliarUseCase(db).execute(usuario_id)


@router.get("/usuarios/{usuario_id}/desempenho")
def get_desempenho(usuario_id: int, semestre_id: Optional[int] = None, current_user=Depends(require_self_or_admin), db: Session = Depends(get_db)):
    result = GetDesempenhoUseCase(db).execute(usuario_id, semestre_id)
    if not result:
        raise HTTPException(status_code=404, detail="Semestre não encontrado")
    return result


# ---------------------------------------------------------------- usuário ↔ frente

@router.post("/usuarios-frentes")
def create_usuario_frente(request: CreateUsuarioFrenteRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """🔒 Vincular-se a uma frente é ação de diretoria.

    A regra antiga ("pode gerenciar as PRÓPRIAS frentes") era um furo no
    recorte de visão: `aplicar_recorte_visao` decide o que um gerente enxerga
    a partir de `usuario_frente`, então o próprio gerente podia se vincular a
    outra frente e passar a ver os projetos dela — burlando o §7.5.
    """
    if not usuario_tem_permissao(current_user, db, "pode_gerenciar_cargos"):
        raise HTTPException(
            status_code=403,
            detail="Apenas a diretoria pode alterar o vínculo de um membro com as frentes",
        )
    return CreateUsuarioFrenteUseCase(db).execute(request)


@router.get("/usuarios-frentes")
def list_usuarios_frentes(db: Session = Depends(get_db)):
    return ListUsuariosFrentesUseCase(db).execute()


@router.get("/usuarios-frentes/{usuario_frente_id}")
def get_usuario_frente(usuario_frente_id: int, db: Session = Depends(get_db)):
    result = GetUsuarioFrenteUseCase(db).execute(usuario_frente_id)
    if not result:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return result


@router.delete("/usuarios-frentes/{usuario_frente_id}", status_code=204)
def delete_usuario_frente(usuario_frente_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    registro = GetUsuarioFrenteUseCase(db).execute(usuario_frente_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    if registro["usuario_id"] != current_user.id and not usuario_tem_permissao(current_user, db, "pode_gerenciar_cargos"):
        raise HTTPException(status_code=403, detail="Você só pode remover suas próprias frentes")
    deleted = DeleteUsuarioFrenteUseCase(db).execute(usuario_frente_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return None
