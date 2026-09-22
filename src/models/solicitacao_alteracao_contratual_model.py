from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.database import Base


class SolicitacaoAlteracaoContratualModel(Base):
    """Um pedido de alteração do CLIENTE sobre um documento jurídico.

    É sobre uma VERSÃO específica (a que o cliente viu na tela de aprovação),
    não sobre o documento em geral — cada "Gerar novo rascunho" cria uma
    versão nova, e um pedido feito sobre uma versão não deve reaparecer como
    pendente na seguinte.

    ⚠ Registrar o pedido NÃO edita o documento sozinho — só sinaliza pro time
    ajustar e gerar de novo (ver `use_cases/documento_contratual/analisar_
    solicitacao.py`).
    """

    __tablename__ = "solicitacao_alteracao_contratual"

    id = Column(Integer, primary_key=True, index=True)
    documento_id = Column(
        Integer, ForeignKey("documento_contratual.id"), nullable=False, index=True
    )
    versao_id = Column(Integer, ForeignKey("documento_contratual_versao.id"), nullable=False)
    texto = Column(Text, nullable=False)
    #: Trechos do documento que o cliente citou ao pedir a alteração (lista
    #: de strings; `None` equivale a `[]`).
    trechos = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pendente")
    criado_em = Column(DateTime, server_default=func.now())

    documento = relationship("DocumentoContratualModel", back_populates="solicitacoes")
    versao = relationship("DocumentoContratualVersaoModel")
