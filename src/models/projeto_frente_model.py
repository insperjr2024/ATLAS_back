from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from src.database.database import Base


class ProjetoFrenteModel(Base):
    """2 linhas = projeto sinérgico (§2) — é o que faz o projeto aparecer para
    os gerentes das duas frentes envolvidas."""

    __tablename__ = "projeto_frente"
    __table_args__ = (UniqueConstraint("projeto_id", "frente_id", name="uq_projeto_frente"),)

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    frente_id = Column(Integer, ForeignKey("frente.id"), nullable=False, index=True)
