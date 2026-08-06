from sqlalchemy import Column, DateTime, Boolean, ForeignKey, Integer, String
from src.database.database import Base


class NotificacaoModel(Base):
    """Central de notificações (§6) — genérica de propósito: hoje só o push
    automático de banca e a confirmação de troca criam linhas aqui, mas o
    modelo não fica preso a banca (kickoff pendente, tarefa vencida etc. são
    outros gatilhos do §6 que podem usar a mesma tabela depois)."""

    __tablename__ = "notificacao"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False)
    mensagem = Column(String(255), nullable=False)
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=True)
    lida = Column(Boolean, default=False, nullable=False)
    criado_em = Column(DateTime, nullable=False)
