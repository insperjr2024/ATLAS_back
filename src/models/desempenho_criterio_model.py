from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Text
from src.database.database import Base


class DesempenhoCriterioModel(Base):
    __tablename__ = "desempenho_criterio"

    id = Column(Integer, primary_key=True, index=True)
    secao_id = Column(Integer, ForeignKey("desempenho_formulario_secao.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(200), nullable=False)
    descricao = Column(Text, nullable=True)
    tipo_resposta = Column(
        Enum("nota", "texto", name="desempenho_criterio_tipo_resposta"),
        nullable=False,
        default="nota",
        server_default="nota",
    )
    limite_caracteres = Column(Integer, nullable=True)
    ordem = Column(Integer, nullable=False, default=0, server_default="0")
