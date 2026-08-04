from sqlalchemy import Column, Date, Enum, ForeignKey, Integer, String, Text
from src.database.database import Base


class ProjetoModel(Base):
    """O cadastro do §6.3. `data_kickoff` nasce vazia — o kickoff ainda não
    existe no registro (§5.1); vazio = alerta de kickoff pendente."""

    __tablename__ = "projeto"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    cliente = Column(String(150), nullable=False)
    descricao = Column(Text, nullable=True)
    link_proposta = Column(String(255), nullable=True)
    status = Column(
        Enum(
            "vendido",
            "ambientacao",
            "em_andamento",
            "validacao_bancas",
            "envio_tep",
            "periodo_ajustes",
            "finalizado",
            "pausado",
            name="status_projeto",
        ),
        nullable=False,
        default="vendido",
        server_default="vendido",
    )
    dias_ambientacao = Column(Integer, nullable=False, default=5, server_default="5")
    data_kickoff = Column(Date, nullable=True)
    data_entrega_cliente = Column(Date, nullable=True)
    dia_reuniao_padrao = Column(Integer, nullable=True)  # 1=seg ... 7=dom
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    # Preserva o status de antes de pausar, para o retomar voltar ao lugar certo
    # sem precisar reconsultar o histórico toda vez.
    status_antes_pausa = Column(String(30), nullable=True)
