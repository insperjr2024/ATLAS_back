from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.sql import func
from src.database.database import Base


class DesempenhoAvaliacaoModel(Base):
    """Uma avaliação de desempenho: `avaliador_id` avaliou `avaliado_id` dentro
    de um lote. `UNIQUE(lote_id, avaliador_id, avaliado_id)` garante que o
    mesmo par não preenche duas vezes no mesmo lote, mesmo que compartilhem
    mais de um projeto (regra 2.3) — diferente da avaliação de banca, aqui não
    existe uma linha por projeto em comum."""

    __tablename__ = "desempenho_avaliacao"
    __table_args__ = (UniqueConstraint("lote_id", "avaliador_id", "avaliado_id", name="uq_desempenho_avaliacao_par"),)

    id = Column(Integer, primary_key=True, index=True)
    lote_id = Column(Integer, ForeignKey("desempenho_lote.id"), nullable=False, index=True)
    formulario_id = Column(Integer, ForeignKey("desempenho_formulario.id"), nullable=False)
    avaliador_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    avaliado_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    nota_geral = Column(Integer, nullable=False)
    comentarios = Column(Text, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
