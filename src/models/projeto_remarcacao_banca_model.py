from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.sql import func
from src.database.database import Base


class ProjetoRemarcacaoBancaModel(Base):
    """§5.6 — toda remarcação de banca já vencida (data antiga trocada por
    nova) fica registrada aqui, com a justificativa obrigatória da diretoria.

    Igual à `ProjetoJustificativaAtrasoModel`: histórico, não campo — uma
    banca remarcada duas vezes gera duas linhas, nenhuma sobrescreve a outra.
    """

    __tablename__ = "projeto_remarcacao_banca"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    banca_id = Column(Integer, ForeignKey("banca.id"), nullable=False)
    #: O escopo da URL da chamada que remarcou — a banca pode cobrir mais de
    #: um, mas foi por este que a ação entrou.
    projeto_escopo_id = Column(Integer, ForeignKey("projeto_escopo.id"), nullable=True)
    data_anterior = Column(DateTime, nullable=False)
    data_nova = Column(DateTime, nullable=False)
    justificativa = Column(Text, nullable=False)
    registrado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    registrado_em = Column(DateTime, nullable=False, server_default=func.now())
