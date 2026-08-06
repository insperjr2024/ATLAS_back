from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.sql import func
from src.database.database import Base


class CronogramaReajusteSolicitacaoModel(Base):
    """§5.6: pedido do coordenador pra reabrir um cronograma já oficializado
    — aprovado ou rejeitado pela diretoria (nunca pelo gerente).

    Aprovar limpa `projeto_escopo.cronograma_oficializado_em` (ver
    `ResponderReajusteUseCase`) — é essa a única saída da trava de
    `cronograma_guard.py`, sem coluna extra e sem estado "meio aberto"."""

    __tablename__ = "cronograma_reajuste_solicitacao"

    id = Column(Integer, primary_key=True, index=True)
    projeto_escopo_id = Column(Integer, ForeignKey("projeto_escopo.id"), nullable=False, index=True)
    solicitado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    motivo = Column(String(500), nullable=False)
    status = Column(
        Enum("pendente", "aprovado", "rejeitado", name="status_reajuste_cronograma"),
        nullable=False,
        default="pendente",
        server_default="pendente",
    )
    respondido_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    resposta_justificativa = Column(String(500), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    respondido_em = Column(DateTime, nullable=True)
