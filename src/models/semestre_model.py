from sqlalchemy import Column, Date, Enum, Integer, String
from src.database.database import Base


class SemestreModel(Base):
    """A gestão semestral (§12). Arquivar = mudar o status, nunca apagar."""

    __tablename__ = "semestre"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(20), nullable=False)
    inicio = Column(Date, nullable=False)
    fim = Column(Date, nullable=False)
    status = Column(
        Enum("ativa", "arquivada", name="status_semestre"),
        nullable=False,
        default="ativa",
        server_default="ativa",
    )