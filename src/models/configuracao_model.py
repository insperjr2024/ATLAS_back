from sqlalchemy import Column, Integer
from src.database.database import Base


class ConfiguracaoModel(Base):
    __tablename__ = "configuracao"

    id = Column(Integer, primary_key=True, index=True)
    vagas_por_banca = Column(Integer, nullable=False, default=5)