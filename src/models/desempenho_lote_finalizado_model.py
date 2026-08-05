from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.sql import func
from src.database.database import Base


class DesempenhoLoteFinalizadoModel(Base):
    """Marca que um usuário já concluiu tudo que tinha pra responder num lote
    (regra 2.4 — só é gravado quando não sobra mais nenhum tipo pendente, ou
    quando a pessoa opta por não responder o restante agora)."""

    __tablename__ = "desempenho_lote_finalizado"
    __table_args__ = (UniqueConstraint("lote_id", "usuario_id", name="uq_desempenho_lote_finalizado"),)

    id = Column(Integer, primary_key=True, index=True)
    lote_id = Column(Integer, ForeignKey("desempenho_lote.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    finalizado_em = Column(DateTime, nullable=False, server_default=func.now())
