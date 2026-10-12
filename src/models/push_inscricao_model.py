"""Notificação push (Web Push): um aparelho/navegador inscrito de uma pessoa.

O navegador gera a inscrição (`PushManager.subscribe`) e o front manda pra
cá: o `endpoint` é a URL do serviço de push do navegador (Apple, Google,
Mozilla) e `p256dh`/`auth` são as chaves com que a mensagem é cifrada pra
aquele aparelho. Uma pessoa pode ter vários aparelhos.

`endpoint` é único: o mesmo aparelho usado por outra pessoa (sair e entrar
com outra conta) troca de dono, não duplica.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from src.database.database import Base


class PushInscricaoModel(Base):
    __tablename__ = "push_inscricao"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = Column(String(1000), nullable=False, unique=True)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(100), nullable=False)
    #: Só pra pessoa reconhecer o aparelho, se um dia houver uma lista.
    user_agent = Column(String(300), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    ultimo_envio_em = Column(DateTime, nullable=True)
