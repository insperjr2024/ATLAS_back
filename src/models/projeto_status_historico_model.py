from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.sql import func
from src.database.database import Base

STATUS_PROJETO_ENUM = Enum(
    "vendido",
    "ambientacao",
    "em_andamento",
    "validacao_bancas",
    "envio_tep",
    "periodo_ajustes",
    "finalizado",
    "pausado",
    name="status_historico_projeto",
)


class ProjetoStatusHistoricoModel(Base):
    """Os timestamps de cada transição (§4): alimentam o "há quanto tempo" do
    monitoramento, o retorno do Pausado e o desconto das janelas pausadas na
    contagem de dias (§5.4)."""

    __tablename__ = "projeto_status_historico"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    status_anterior = Column(STATUS_PROJETO_ENUM, nullable=True)  # vazio na criação
    status_novo = Column(STATUS_PROJETO_ENUM, nullable=False)
    alterado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)  # vazio = automático
    alterado_em = Column(DateTime, nullable=False, server_default=func.now())
