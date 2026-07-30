from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from src.database.database import Base


class AvaliacaoModel(Base):
    __tablename__ = "avaliacao"

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False)
    avaliador_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    formulario_id = Column(Integer, ForeignKey("formulario.id"), nullable=False)
    status = Column(String(20), nullable=False, default="rascunho")
    comentario_feedback = Column(String(1000), nullable=True)
    submetida_em = Column(DateTime, nullable=True)