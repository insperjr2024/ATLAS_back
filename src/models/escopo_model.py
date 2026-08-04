from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from src.database.database import Base


class EscopoModel(Base):
    """Catálogo de escopos por frente (§4).

    Era uma lista plana usada como rótulo da banca; vira o catálogo dono da
    frente. A opção "Outro" NÃO entra aqui — é nome digitado direto no escopo
    vendido do projeto (`projeto_escopo.nome_customizado`).

    `frente_id` nasce nullable por causa das linhas já cadastradas, que não têm
    frente. O seed preenche as do catálogo padrão.
    """

    __tablename__ = "escopo"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    frente_id = Column(Integer, ForeignKey("frente.id"), nullable=True, index=True)
    ativo = Column(Boolean, nullable=False, default=True, server_default="1")