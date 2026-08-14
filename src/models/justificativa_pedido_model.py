from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from src.database.database import Base


class JustificativaPedidoModel(Base):
    """§7.4: a diretoria **pergunta** ao coordenador por que o escopo atrasou.

    ⭐ **O §7.4 descreve uma conversa, não um campo.** "A justificativa é
    registrada pela diretoria: ela pergunta ao coordenador e digita a nota."
    A plataforma tinha só a segunda metade — a caixa de texto — e a primeira
    acontecia por fora, no WhatsApp. Quem perguntou, quando, e se já
    responderam não existia em lugar nenhum: a diretora abria a fila na semana
    seguinte sem saber se aquele atraso já tinha sido cobrado.

    ⚠ **Não substitui a nota direta.** A diretoria continua podendo escrever o
    porquê quando já sabe — pedir é o caminho de quando ela NÃO sabe. Os dois
    convivem na mesma linha da fila de Aprovações.

    O pedido é do MOTIVO, não do projeto: `projeto_escopo_id` + `tipo` são a
    mesma chave que `justificativa_cobrindo` usa para decidir o que já foi
    respondido. Um projeto com dois escopos atrasados rende dois pedidos, e
    responder um não fecha o outro.
    """

    __tablename__ = "justificativa_pedido"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    #: Nulo = pedido geral do projeto (nenhum escopo específico).
    projeto_escopo_id = Column(Integer, ForeignKey("projeto_escopo.id"), nullable=True)
    #: "banca", "escopo"… Nulo = qualquer motivo daquele escopo.
    tipo = Column(String(30), nullable=True)

    solicitado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    solicitado_em = Column(DateTime, nullable=False, server_default=func.now())

    #: `None` = ainda esperando o coordenador. Preenchido quando a nota chega.
    respondido_em = Column(DateTime, nullable=True)
    #: A nota que respondeu — o link do "já respondido" para o histórico.
    justificativa_id = Column(
        Integer, ForeignKey("projeto_justificativa_atraso.id"), nullable=True
    )
