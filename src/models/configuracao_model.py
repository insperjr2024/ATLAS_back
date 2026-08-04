from sqlalchemy import Column, Integer, ForeignKey
from src.database.database import Base


class ConfiguracaoModel(Base):
    __tablename__ = "configuracao"

    id = Column(Integer, primary_key=True, index=True)
    vagas_por_banca = Column(Integer, nullable=False, default=5)
    cargo_padrao_id = Column(Integer, ForeignKey("cargo.id"), nullable=True)