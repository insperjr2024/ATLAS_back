from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from src.database.database import Base


class DesempenhoLoteProjetoModel(Base):
    """Quais projetos um lote de desempenho cobre."""

    __tablename__ = "desempenho_lote_projeto"
    __table_args__ = (UniqueConstraint("lote_id", "projeto_id", name="uq_desempenho_lote_projeto"),)

    id = Column(Integer, primary_key=True, index=True)
    lote_id = Column(Integer, ForeignKey("desempenho_lote.id", ondelete="CASCADE"), nullable=False, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
