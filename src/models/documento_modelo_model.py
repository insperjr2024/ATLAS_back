from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.sql import func
from src.database.database import Base


class DocumentoModeloModel(Base):
    """Modelo base (.docx) de um tipo de documento jurídico, quando a
    diretoria trocou o que vem no deploy (2026-10-07, a pedido).

    Sem linha pro tipo, a geração usa o arquivo de
    `documentos_contratuais/templates/`. Com linha, usa este conteúdo. O
    modelo enviado precisa manter os mesmos campos do padrão (a validação
    está em `use_cases/documento_contratual/modelos.py`): o que muda é o
    texto em volta, nunca o que o preenchimento precisa fornecer.
    """

    __tablename__ = "documento_modelo"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(20), nullable=False, unique=True)
    arquivo_nome = Column(String(255), nullable=False)
    arquivo_conteudo = Column(LargeBinary, nullable=False)
    enviado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    enviado_em = Column(DateTime, nullable=False, server_default=func.now())
