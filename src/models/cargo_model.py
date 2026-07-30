from sqlalchemy import Column, Integer, String, Boolean
from src.database.database import Base


class CargoModel(Base):
    __tablename__ = "cargo"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    pode_definir_formulario = Column(Boolean, default=False, nullable=False)
    pode_agendar_banca = Column(Boolean, default=False, nullable=False)
    pode_gerenciar_cargos = Column(Boolean, default=False, nullable=False)