from sqlalchemy import Column, Date, Enum, ForeignKey, Integer, String, UniqueConstraint
from src.database.database import Base


class DiaNaoLetivoModel(Base):
    """Calendário acadêmico do Insper, carregado a cada semestre.

    📐 É esta tabela que define o que é dia útil: seg–sex que NÃO está aqui.
    """

    __tablename__ = "dia_nao_letivo"
    __table_args__ = (
        UniqueConstraint(
            "semestre_id", "frente_id", "data", name="uq_dia_nao_letivo_semestre_frente_data"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    semestre_id = Column(Integer, ForeignKey("semestre.id"), nullable=False, index=True)
    #: A frente dona deste dia. `NULL` = vale para TODAS as frentes.
    #:
    #: Cada frente abrange cursos diferentes, e cada curso tem o seu calendário
    #: acadêmico — o de Business não é o de Tech. O nulo continua existindo para
    #: o que é da faculdade inteira (feriado nacional, por exemplo) e para não
    #: invalidar a carga que já estava no banco antes desta coluna.
    frente_id = Column(Integer, ForeignKey("frente.id"), nullable=True, index=True)
    data = Column(Date, nullable=False, index=True)
    tipo = Column(Enum("feriado", "prova", "recesso", name="tipo_dia_nao_letivo"), nullable=False)
    descricao = Column(String(150), nullable=True)
