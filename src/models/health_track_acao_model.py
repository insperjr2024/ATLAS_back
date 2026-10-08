"""Ações do Health Track (§15): o Health Track não termina no diagnóstico.

Todo problema relevante pode virar `problema -> responsável -> próxima ação
-> prazo`, preso ao projeto (e, se fizer sentido, a um pilar). A ação fica
aberta até alguém concluir; concluída continua no histórico do projeto.
"""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy.sql import func
from src.database.database import Base


class HealthTrackAcaoModel(Base):
    __tablename__ = "health_track_acao"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id", ondelete="CASCADE"), nullable=False, index=True)
    #: Opcional: a qual pilar o problema se refere.
    pilar_id = Column(Integer, ForeignKey("health_track_pilar.id"), nullable=True)
    problema = Column(Text, nullable=False)
    proxima_acao = Column(Text, nullable=False)
    responsavel_id = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    prazo = Column(Date, nullable=True)
    concluida_em = Column(DateTime, nullable=True)
    concluida_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
