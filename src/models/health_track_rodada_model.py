"""Rodadas do Health Track (2026-10-08, a pedido da diretoria de projetos).

A diretoria não queria uma cadência automática ("de 15 em 15 dias"): tem
semana sem reunião de projetos e a contagem desandaria. Quem decide "hoje é
dia" é a diretora, clicando em ABRIR RODADA. A rodada congela a lista dos
projetos em acompanhamento naquele momento e só CONCLUI quando cada um
deles foi avaliado ou teve a falta justificada ("está pausado", "não faz
sentido agora"). Enquanto isso, o que ficou pra trás aparece em vermelho na
página, pra ninguém esquecer.

Uma rodada aberta por vez. A avaliação em si continua sendo a de sempre
(`health_track_avaliacao`); a rodada só diz quais projetos faltavam e o que
aconteceu com cada um.
"""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.sql import func
from src.database.database import Base

SITUACOES_RODADA = ("pendente", "avaliada", "justificada")


class HealthTrackRodadaModel(Base):
    __tablename__ = "health_track_rodada"

    id = Column(Integer, primary_key=True, index=True)
    aberta_em = Column(DateTime, nullable=False, server_default=func.now())
    aberta_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    #: Vazio enquanto a rodada está em andamento.
    concluida_em = Column(DateTime, nullable=True)
    concluida_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)


class HealthTrackRodadaProjetoModel(Base):
    """Um projeto dentro de uma rodada e o que aconteceu com ele."""

    __tablename__ = "health_track_rodada_projeto"
    __table_args__ = (UniqueConstraint("rodada_id", "projeto_id", name="uq_health_track_rodada_projeto"),)

    id = Column(Integer, primary_key=True, index=True)
    rodada_id = Column(
        Integer, ForeignKey("health_track_rodada.id", ondelete="CASCADE"), nullable=False, index=True
    )
    projeto_id = Column(Integer, ForeignKey("projeto.id", ondelete="CASCADE"), nullable=False, index=True)
    situacao = Column(
        Enum(*SITUACOES_RODADA, name="situacao_health_track_rodada"),
        nullable=False,
        default="pendente",
        server_default="pendente",
    )
    #: Por que não foi avaliado nesta rodada. Só com `situacao = justificada`.
    justificativa = Column(Text, nullable=True)
    #: Quando saiu de pendente (a hora da avaliação, ou da justificativa).
    resolvido_em = Column(DateTime, nullable=True)
    resolvido_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
