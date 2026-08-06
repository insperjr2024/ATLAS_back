from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.notificacao_repository import NotificacaoRepository


def notificar(db: Session, usuario_id: int, mensagem: str, banca_id: Optional[int] = None) -> None:
    """Central de notificações (§6) — cria a linha; a listagem é responsabilidade
    de quem lê (`GET /notificacoes`), não deste helper."""
    NotificacaoRepository(db).create(
        usuario_id=usuario_id, mensagem=mensagem, criado_em=datetime.now(), banca_id=banca_id
    )
