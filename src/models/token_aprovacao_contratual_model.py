from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.database import Base


class TokenAprovacaoContratualModel(Base):
    """Link público de aprovação, de uso único.

    Aponta para o DOCUMENTO JURÍDICO (o que está sendo aprovado) e para a
    VERSÃO (o arquivo exato que o cliente viu). `projeto_id` não mora aqui —
    vem de `token.documento.projeto_id`.
    """

    __tablename__ = "token_aprovacao_contratual"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    documento_id = Column(
        Integer, ForeignKey("documento_contratual.id"), nullable=False, index=True
    )
    versao_id = Column(Integer, ForeignKey("documento_contratual_versao.id"), nullable=False)
    usado = Column(Boolean, nullable=False, default=False)
    criado_em = Column(DateTime, server_default=func.now())

    documento = relationship("DocumentoContratualModel", back_populates="tokens")
    versao = relationship("DocumentoContratualVersaoModel")
