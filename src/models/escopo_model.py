from sqlalchemy import Column, Integer, String
from src.database.database import Base


class EscopoModel(Base):
    __tablename__ = "escopo"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)