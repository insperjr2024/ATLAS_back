from sqlalchemy.orm import Session
from src.models.notificacao_model import NotificacaoModel
from typing import List, Optional
from datetime import datetime


class NotificacaoRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, usuario_id: int, mensagem: str, criado_em: datetime,
               banca_id: Optional[int] = None) -> NotificacaoModel:
        notificacao = NotificacaoModel(
            usuario_id=usuario_id,
            mensagem=mensagem,
            banca_id=banca_id,
            criado_em=criado_em,
        )
        self.db.add(notificacao)
        self.db.commit()
        self.db.refresh(notificacao)
        return notificacao

    def get_by_id(self, notificacao_id: int) -> Optional[NotificacaoModel]:
        return self.db.query(NotificacaoModel).filter(NotificacaoModel.id == notificacao_id).first()

    def get_by_usuario(self, usuario_id: int) -> List[NotificacaoModel]:
        return self.db.query(NotificacaoModel).filter(NotificacaoModel.usuario_id == usuario_id).all()

    def update(self, notificacao_id: int, **kwargs) -> Optional[NotificacaoModel]:
        notificacao = self.get_by_id(notificacao_id)
        if not notificacao:
            return None
        for key, value in kwargs.items():
            setattr(notificacao, key, value)
        self.db.commit()
        self.db.refresh(notificacao)
        return notificacao
