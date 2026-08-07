from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from src.database.database import Base


class SolicitacaoTrocaModel(Base):
    """Pedido aberto de troca de candidatura (§8): quem não pode comparecer
    abre o pedido, qualquer consultor elegível confirma e assume a vaga.

    `banca_id`/`usuario_original_id` são gravados na criação e não dependem
    de `candidatura_id` continuar existindo — confirmar a troca apaga a
    candidatura antiga, e o histórico (quem pediu, quem confirmou) precisa
    sobreviver a isso. Por isso `candidatura_id` é `SET NULL`, não `CASCADE`.
    """

    __tablename__ = "solicitacao_troca"

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False)
    usuario_original_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    candidatura_id = Column(
        Integer, ForeignKey("candidatura.id", ondelete="SET NULL"), nullable=True
    )
    #: Nulo = pedido aberto, qualquer elegível confirma. Preenchido = convite
    #: pra uma pessoa específica — só ela pode confirmar (ver
    #: `ConfirmarSolicitacaoTrocaUseCase`).
    usuario_convidado_id = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    status = Column(
        Enum("pendente", "confirmada", "cancelada", name="status_solicitacao_troca"),
        default="pendente",
        nullable=False,
    )
    criado_em = Column(DateTime, nullable=False)
    confirmada_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    confirmada_em = Column(DateTime, nullable=True)
