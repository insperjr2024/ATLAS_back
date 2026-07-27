from sqlalchemy import Column, Integer, String, Date, Numeric
from src.database.database import Base


class SemestreModel(Base):
    __tablename__ = "semestre"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(20), nullable=False)
    inicio = Column(Date, nullable=False)
    fim = Column(Date, nullable=False)