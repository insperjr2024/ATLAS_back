from sqlalchemy import Boolean, Column, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.sql import func
from src.database.database import Base


class HealthTrackPilarModel(Base):
    """Os pilares em que a saúde de um projeto é avaliada (Health Track §2).

    São dados, não código: a diretoria vai renomear, reordenar e desativar
    pilares sem deploy (§18). Os 6 iniciais nascem na migration.

    **Desativar, nunca apagar.** As avaliações antigas apontam para o pilar
    e são o histórico que alimenta evolução e persistência (§7, §16) — apagar
    o pilar levaria esse histórico junto. Pilar inativo some da listagem e
    deixa de ser exigido no preenchimento, mas continua no histórico.
    """

    __tablename__ = "health_track_pilar"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(60), nullable=False, unique=True)
    descricao = Column(Text, nullable=True)
    ordem = Column(SmallInteger, nullable=False, default=0, server_default="0")
    ativo = Column(Boolean, nullable=False, default=True, server_default="1")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
