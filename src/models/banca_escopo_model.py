from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from src.database.database import Base


class BancaEscopoModel(Base):
    """Quais escopos vendidos uma banca cobre.

    Antes o vínculo era a coluna `banca.projeto_escopo_id`, UNIQUE: uma banca
    para exatamente um escopo. A regra mudou — uma banca pode avaliar vários
    escopos do projeto de uma sentada, e quem escolhe quais é a coordenação,
    na hora de marcar.

    ⭐ O UNIQUE trocou de lado, não sumiu: continua valendo que **um escopo tem
    no máximo uma banca**. É isso que mantém `escopo.banca` sendo um objeto (e
    não uma lista) em toda a leitura, e que deixa a trava de entrega do §5.5
    sem ambiguidade — um resultado só decide se a entrega abre.

    Não há espelho de `banca.projeto_escopo_id`: a coluna foi removida na
    migration que criou esta tabela. Vínculo mora num lugar só.
    """

    __tablename__ = "banca_escopo"
    __table_args__ = (
        UniqueConstraint("projeto_escopo_id", name="uq_banca_escopo_projeto_escopo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(
        Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False, index=True
    )
    projeto_escopo_id = Column(
        Integer,
        ForeignKey("projeto_escopo.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
