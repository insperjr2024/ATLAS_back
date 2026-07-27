from sqlalchemy import Column, Integer, String
from src.database.database import Base


class FrenteModel(Base):
    __tablename__ = "frente"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(50), nullable=False)