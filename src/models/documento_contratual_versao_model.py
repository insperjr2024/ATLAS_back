from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.database import Base


class DocumentoContratualVersaoModel(Base):
    """Um ARQUIVO gerado: uma linha por versão de .docx/.pdf.

    Pertence a um `DocumentoContratualModel`, que é quem carrega o workflow.
    Cada "Gerar novo rascunho" cria mais uma linha aqui, com `versao`
    incrementada.

    `projeto_id` e `tipo` não vivem aqui: são do documento (`documento.
    projeto_id`, `documento.tipo`) — mantê-los duplicados abriria espaço pra
    divergirem.
    """

    __tablename__ = "documento_contratual_versao"

    id = Column(Integer, primary_key=True, index=True)
    documento_id = Column(
        Integer, ForeignKey("documento_contratual.id"), nullable=False, index=True
    )
    versao = Column(Integer, nullable=False, default=1)
    status_arquivo = Column(String(20), nullable=False, default="rascunho")
    #: Preenchido só quando o documento vira final assinado — a gestão em que
    #: foi arquivado.
    gestao_id = Column(Integer, ForeignKey("semestre.id"), nullable=True)
    docx_path = Column(String(500), nullable=False)
    pdf_path = Column(String(500), nullable=False)
    criado_em = Column(DateTime, server_default=func.now())
    #: Preenchido só quando o documento vira final assinado — data real em
    #: que a assinatura foi confirmada na plataforma, distinta de `criado_em`
    #: (quando esse rascunho foi gerado, podendo ser bem anterior à
    #: assinatura).
    arquivado_em = Column(DateTime, nullable=True)

    documento = relationship("DocumentoContratualModel", back_populates="versoes")
