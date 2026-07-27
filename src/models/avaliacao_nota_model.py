from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from src.database.database import Base


class AvaliacaoNotaModel(Base):
    __tablename__ = "avaliacao_nota"

    id = Column(Integer, primary_key=True, index=True)
    avaliacao_id = Column(Integer, ForeignKey("avaliacao.id"), nullable=False)
    pergunta_id = Column(Integer, ForeignKey("pergunta.id"), nullable=False)
    nota = Column(Numeric(2, 1), nullable=True)
    resposta_texto = Column(String(1000), nullable=True)