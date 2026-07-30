from sqlalchemy import Column, Integer, ForeignKey
from src.database.database import Base


class EquipeProjetoModel(Base):
    __tablename__ = "equipe_projeto"

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)