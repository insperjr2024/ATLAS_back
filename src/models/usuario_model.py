from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from src.database.database import Base


class UsuarioModel(Base):
    __tablename__ = "usuario"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    email_insper = Column(String(150), unique=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    cargo_id = Column(Integer, ForeignKey("cargo.id"), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)