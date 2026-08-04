from sqlalchemy import Column, Integer, String, ForeignKey
from src.database.database import Base


class PerguntaModel(Base):
    __tablename__ = "pergunta"

    id = Column(Integer, primary_key=True, index=True)
    formulario_id = Column(Integer, ForeignKey("formulario.id"), nullable=False)
    texto = Column(String(500), nullable=False)
    ordem = Column(Integer, nullable=False)
    tipo_resposta = Column(String(20), nullable=False, default="nota")