from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from src.database.database import Base


class DesempenhoLoteFormularioModel(Base):
    """A versão de formulário que um lote usa pra um papel, quando não é a
    vigente. Só existe linha depois que alguém editou o formulário com o
    lote aberto e escolheu "só pra futuros". Sem linha = o lote usa a
    vigente, como sempre foi."""

    __tablename__ = "desempenho_lote_formulario"
    __table_args__ = (UniqueConstraint("lote_id", "papel", name="uq_desempenho_lote_formulario"),)

    id = Column(Integer, primary_key=True, index=True)
    lote_id = Column(Integer, ForeignKey("desempenho_lote.id", ondelete="CASCADE"), nullable=False, index=True)
    papel = Column(String(20), nullable=False)
    formulario_id = Column(Integer, ForeignKey("desempenho_formulario.id"), nullable=False, index=True)
