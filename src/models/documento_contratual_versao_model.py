from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String
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

    ⚠ 2026-09-18 — o conteúdo mora no BANCO (`LargeBinary`), não um caminho de
    arquivo no disco do servidor. Mesmo padrão de `ProjetoModel.
    anexo_proposta_conteudo`: o disco de produção já demonstrou não ser
    confiável entre deploys (o PDF da proposta sumiu assim uma vez, com o
    nome ainda registrado no banco apontando pra um arquivo que não existia
    mais). Documento jurídico assinado é mais sensível que uma proposta de
    venda — não repetir o mesmo erro aqui. A geração ainda passa por um
    arquivo temporário (o LibreOffice só converte a partir de disco), mas
    nada além do request sobrevive fora do banco.
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
    docx_conteudo = Column(LargeBinary, nullable=False)
    pdf_conteudo = Column(LargeBinary, nullable=False)
    criado_em = Column(DateTime, server_default=func.now())
    #: Preenchido só quando o documento vira final assinado — data real em
    #: que a assinatura foi confirmada na plataforma, distinta de `criado_em`
    #: (quando esse rascunho foi gerado, podendo ser bem anterior à
    #: assinatura).
    arquivado_em = Column(DateTime, nullable=True)

    documento = relationship("DocumentoContratualModel", back_populates="versoes")
