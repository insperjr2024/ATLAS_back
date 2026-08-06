"""Central de notificações (§6) — cada usuário só enxerga as suas."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.validate_user_auth_token import get_current_user
from src.repositories.notificacao_repository import NotificacaoRepository

router = APIRouter(tags=["notificações"], dependencies=[Depends(get_current_user)])


def _serializar(n):
    return {
        "id": n.id,
        "usuario_id": n.usuario_id,
        "mensagem": n.mensagem,
        "banca_id": n.banca_id,
        "lida": n.lida,
        "criado_em": n.criado_em,
    }


@router.get("/notificacoes")
def list_notificacoes(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    notificacoes = NotificacaoRepository(db).get_by_usuario(current_user.id)
    return [_serializar(n) for n in sorted(notificacoes, key=lambda n: n.criado_em, reverse=True)]


@router.patch("/notificacoes/{notificacao_id}")
def marcar_lida(notificacao_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    repository = NotificacaoRepository(db)
    existente = repository.get_by_id(notificacao_id)
    if not existente:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    if existente.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="Você só pode marcar suas próprias notificações")
    notificacao = repository.update(notificacao_id, lida=True)
    return _serializar(notificacao)
