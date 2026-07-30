from sqlalchemy import Column, Integer, ForeignKey
from src.database.database import Base


class BancaFrenteModel(Base):
    __tablename__ = "banca_frente"

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False)
    frente_id = Column(Integer, ForeignKey("frente.id"), nullable=False)