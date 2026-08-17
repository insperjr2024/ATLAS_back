"""Usuários, o vínculo N:N com frentes e os indicadores pessoais."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    require_diretor,
    require_pode_gerir_membros,
    require_self_or_admin,
    usuario_tem_permissao,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.auth.senha_provisoria import ReenviarSenhaProvisoriaUseCase
from src.use_cases.banca.get_bancas_para_avaliar import GetBancasParaAvaliarUseCase
from src.use_cases.usuario.atualizar_foto import (
    AtualizarFotoUsuarioUseCase,
    RemoverFotoUsuarioUseCase,
)
from src.use_cases.usuario.atualizar_preferencia_notificacao import (
    AtualizarPreferenciaNotificacaoRequest,
    AtualizarPreferenciaNotificacaoUseCase,
)
from src.use_cases.usuario.get_desempenho import GetDesempenhoUseCase
from src.use_cases.usuario.get_usuario import GetUsuarioUseCase, ListUsuariosUseCase
from src.use_cases.usuario.transferir_diretoria import (
    TransferirDiretoriaUseCase,
    TransferirDiretoriaRequest,
)
from src.use_cases.usuario.update_usuario import UpdateUsuarioUseCase, UpdateUsuarioRequest, DeleteUsuarioUseCase
from src.use_cases.usuario.delete_usuario_permanente import DeleteUsuarioPermanenteUseCase
from src.use_cases.usuario_frente.create_usuario_frente import CreateUsuarioFrenteUseCase, CreateUsuarioFrenteRequest
from src.use_cases.usuario_frente.get_usuario_frente import GetUsuarioFrenteUseCase, ListUsuariosFrentesUseCase
from src.use_cases.usuario_frente.update_usuario_frente import DeleteUsuarioFrenteUseCase
from src.utils.exceptions import RegraDeNegocioError, ResourceInUseError

router = APIRouter(tags=["usuários"], dependencies=[Depends(get_current_user)])


class AtualizarFotoRequest(BaseModel):
    foto: str


# ---------------------------------------------------------------- usuários

@router.put("/usuarios/me/foto")
def atualizar_minha_foto(
    request: AtualizarFotoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sempre a PRÓPRIA foto, nunca a de outra pessoa — ver `atualizar_foto.py`."""
    try:
        return AtualizarFotoUsuarioUseCase(db).execute(current_user, request.foto)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/usuarios/me/foto")
def remover_minha_foto(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return RemoverFotoUsuarioUseCase(db).execute(current_user)


@router.patch("/usuarios/me/notificacoes-email")
def atualizar_minhas_notificacoes_email(
    request: AtualizarPreferenciaNotificacaoRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sempre a PRÓPRIA preferência — mesmo espírito de `/usuarios/me/foto`."""
    try:
        return AtualizarPreferenciaNotificacaoUseCase(db).execute(current_user.id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    current_user=Depends(require_pode_gerir_membros),
    db: Session = Depends(get_db),
):
    try:
        result = UpdateUsuarioUseCase(db).execute(usuario_id, request, alterado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return result


@router.post("/usuarios/transferir-diretoria")
def transferir_diretoria(
    request: TransferirDiretoriaRequest,
    current_user=Depends(require_diretor),
    db: Session = Depends(get_db),
):
    """§10 — a passagem de bastão da virada de gestão, num passo só.

    🔒 Restrita à diretoria por posição: é a ação que decide quem manda no
    ano seguinte.
    """
    try:
        return TransferirDiretoriaUseCase(db).execute(request, alterado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/usuarios/{usuario_id}/senha-provisoria")
def reenviar_senha_provisoria(
    usuario_id: int,
    _=Depends(require_diretor),
    db: Session = Depends(get_db),
):
    """Reemite a senha de primeiro acesso e manda de novo por e-mail.

    🔒 Diretoria, a mesma régua do cadastro — e não `pode_gerir_membros`:
    reenviar DERRUBA a senha atual da pessoa, então quem pudesse fazer isso
    entraria na conta de qualquer um, inclusive de um diretor.

    A senha em claro volta na resposta porque é a única chance de vê-la: quem
    reemitiu consegue repassá-la se o e-mail não sair (`email_enviado: false`).
    """
    try:
        resultado = ReenviarSenhaProvisoriaUseCase(db).execute(usuario_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not resultado:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return resultado


@router.delete("/usuarios/{usuario_id}", status_code=204)
def delete_usuario(usuario_id: int, _=Depends(require_pode_gerir_membros), db: Session = Depends(get_db)):
    try:
        deleted = DeleteUsuarioUseCase(db).execute(usuario_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a este usuário")
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return None


@router.delete("/usuarios/{usuario_id}/permanente")
def delete_usuario_permanente(usuario_id: int, _=Depends(require_diretor), db: Session = Depends(get_db)):
    """Apagar de vez — só um usuário já desligado, e sem volta. Restrito à
    diretoria: cascata bem mais pesada que a exclusão simples acima."""
    try:
        result = DeleteUsuarioPermanenteUseCase(db).execute(usuario_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return result


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
    if not usuario_tem_permissao(current_user, db, "pode_gerir_membros"):
        raise HTTPException(
            status_code=403,
            detail="Apenas a diretoria pode alterar o vínculo de um membro com as frentes",
        )
    try:
        return CreateUsuarioFrenteUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    if registro["usuario_id"] != current_user.id and not usuario_tem_permissao(current_user, db, "pode_gerir_membros"):
        raise HTTPException(status_code=403, detail="Você só pode remover suas próprias frentes")
    deleted = DeleteUsuarioFrenteUseCase(db).execute(usuario_frente_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return None
