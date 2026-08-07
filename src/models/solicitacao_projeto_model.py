from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func
from src.database.database import Base


class SolicitacaoProjetoModel(Base):
    """Declaração de interesse de um consultor em entrar num projeto.

    📐 O pedido NÃO é apagado quando respondido — vira `aprovada` ou
    `recusada` e fica. É o histórico de quem quis entrar onde, e de quem
    decidiu: sem isso, um consultor recusado três vezes seguidas não aparece
    em lugar nenhum.

    📐 Quem responde é o COORDENADOR do projeto, e aprovar já inclui a pessoa
    na equipe. É um poder novo e estreito: ele não ganha `pode_editar_equipe`,
    só a capacidade de aceitar quem pediu para entrar no projeto dele.
    """

    __tablename__ = "solicitacao_projeto"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(
        Integer, ForeignKey("projeto.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    #: Por que a pessoa quer entrar. Obrigatória — é o que o coordenador lê
    #: para decidir, e sem ela o pedido vira um botão sem informação.
    justificativa = Column(String(1000), nullable=False)
    status = Column(
        Enum("pendente", "aprovada", "recusada", name="status_solicitacao_projeto"),
        nullable=False,
        default="pendente",
        server_default="pendente",
    )
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    #: Quem respondeu e quando. Nulos enquanto o pedido está pendente.
    respondido_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    respondido_em = Column(DateTime, nullable=True)
    #: O motivo da recusa, escrito pelo coordenador. Opcional — recusar sem
    #: explicar é ruim, mas obrigar texto faria o coordenador escrever "não"
    #: só para passar da validação.
    resposta = Column(String(500), nullable=True)
