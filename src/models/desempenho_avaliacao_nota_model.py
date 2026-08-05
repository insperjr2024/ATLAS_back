from sqlalchemy import Column, ForeignKey, Integer, Text
from src.database.database import Base


class DesempenhoAvaliacaoNotaModel(Base):
    """1 linha por critério dentro de uma avaliação. `nota` é usado quando o
    critério é do tipo "nota" (1-5); `resposta_texto`, quando é do tipo
    "texto" — nunca os dois preenchidos na mesma linha."""

    __tablename__ = "desempenho_avaliacao_nota"

    id = Column(Integer, primary_key=True, index=True)
    avaliacao_id = Column(Integer, ForeignKey("desempenho_avaliacao.id", ondelete="CASCADE"), nullable=False, index=True)
    criterio_id = Column(Integer, ForeignKey("desempenho_criterio.id"), nullable=False, index=True)
    nota = Column(Integer, nullable=True)
    resposta_texto = Column(Text, nullable=True)
