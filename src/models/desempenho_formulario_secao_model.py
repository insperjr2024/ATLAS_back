from sqlalchemy import Column, ForeignKey, Integer, String, Text
from src.database.database import Base


class DesempenhoFormularioSecaoModel(Base):
    __tablename__ = "desempenho_formulario_secao"

    id = Column(Integer, primary_key=True, index=True)
    formulario_id = Column(Integer, ForeignKey("desempenho_formulario.id", ondelete="CASCADE"), nullable=False, index=True)
    titulo = Column(String(200), nullable=False)
    descricao = Column(Text, nullable=True)
    ordem = Column(Integer, nullable=False, default=0, server_default="0")
