from sqlalchemy import Column, Integer, ForeignKey
from src.database.database import Base


class UsuarioFrenteModel(Base):
    __tablename__ = "usuario_frente"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    frente_id = Column(Integer, ForeignKey("frente.id"), nullable=False)