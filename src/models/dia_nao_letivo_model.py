from sqlalchemy import Column, Date, Enum, ForeignKey, Integer, String, UniqueConstraint
from src.database.database import Base


class DiaNaoLetivoModel(Base):
    """Calendário acadêmico do Insper, carregado a cada semestre.

    📐 É esta tabela que define o que é dia útil: seg–sex que NÃO está aqui.
    """

    __tablename__ = "dia_nao_letivo"
    __table_args__ = (UniqueConstraint("semestre_id", "data", name="uq_dia_nao_letivo_semestre_data"),)

    id = Column(Integer, primary_key=True, index=True)
    semestre_id = Column(Integer, ForeignKey("semestre.id"), nullable=False, index=True)
    data = Column(Date, nullable=False, index=True)
    tipo = Column(Enum("feriado", "prova", "recesso", name="tipo_dia_nao_letivo"), nullable=False)
    descricao = Column(String(150), nullable=True)
