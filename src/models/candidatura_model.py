from sqlalchemy import Column, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint
from src.database.database import Base


class CandidaturaModel(Base):
    __tablename__ = "candidatura"
    # Nunca duas linhas da mesma pessoa na mesma banca (2026-09-16): nada no
    # use case impedia clicar "Alocar-se" duas vezes (ou a gestão adicionar a
    # mesma pessoa de novo) antes desta trava — foi assim que uma consultora
    # apareceu 4x na ficha do GELATTO, e alguém teve que apagar à mão.
    __table_args__ = (
        UniqueConstraint("banca_id", "usuario_id", name="uq_candidatura_banca_usuario"),
    )

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    criado_em = Column(DateTime, nullable=False)
    confirmado = Column(Boolean, default=False, nullable=False)