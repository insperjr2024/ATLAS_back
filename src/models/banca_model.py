from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from src.database.database import Base


class BancaModel(Base):
    __tablename__ = "banca"

    id = Column(Integer, primary_key=True, index=True)
    nome_projeto = Column(String(150), nullable=False)
    escopo_id = Column(Integer, ForeignKey("escopo.id"), nullable=False)
    coordenador_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    data_hora = Column(DateTime, nullable=True)
    status = Column(String(30), nullable=False)
    nota_final = Column(Numeric(3, 2), nullable=True)