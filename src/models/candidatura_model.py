from sqlalchemy import Column, Integer, DateTime, Boolean, ForeignKey
from src.database.database import Base


class CandidaturaModel(Base):
    __tablename__ = "candidatura"

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    criado_em = Column(DateTime, nullable=False)
    confirmado = Column(Boolean, default=False, nullable=False)