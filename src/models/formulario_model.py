from sqlalchemy import Column, Integer, Boolean, ForeignKey
from src.database.database import Base


class FormularioModel(Base):
    __tablename__ = "formulario"

    id = Column(Integer, primary_key=True, index=True)
    semestre_id = Column(Integer, ForeignKey("semestre.id"), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)