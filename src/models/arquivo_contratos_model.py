"""Arquivo de contratos (2026-10-07, a pedido): a "pasta compartilhada" da
Insper Jr com os contratos assinados, mais o que a diretoria importar de
fora do ATLAS.

Estrutura automática: uma pasta raiz por gestão (semestre), e dentro dela
uma pasta por projeto. Quem tem a caixa `pode_acessar_arquivo_contratos`
também cria pastas livres em qualquer nível, importa, renomeia, move,
substitui e apaga, como num drive.

Contrato assinado e arquivado no kanban entra sozinho em Gestão/Projeto,
com o PDF da última versão e o nome "PROJETO - Tipo.pdf". Apagar o
documento no kanban não tira o arquivo daqui: ele ganha "[DELETADO] " na
frente do nome e perde o vínculo (`documento_id` fica nulo).
"""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.sql import func
from src.database.database import Base


class ArquivoContratosPastaModel(Base):
    __tablename__ = "arquivo_contratos_pasta"
    __table_args__ = (
        # Uma pasta por gestão na raiz e uma por projeto dentro de cada gestão:
        # é o que deixa o arquivamento automático achar a pasta certa.
        UniqueConstraint("semestre_id", name="uq_arquivo_contratos_pasta_semestre"),
        UniqueConstraint("pai_id", "projeto_id", name="uq_arquivo_contratos_pasta_projeto"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    pai_id = Column(Integer, ForeignKey("arquivo_contratos_pasta.id", ondelete="CASCADE"), nullable=True, index=True)
    #: Pasta raiz de uma gestão (criada sozinha).
    semestre_id = Column(Integer, ForeignKey("semestre.id", ondelete="SET NULL"), nullable=True)
    #: Pasta de um projeto dentro da gestão (criada sozinha no 1º arquivamento).
    projeto_id = Column(Integer, ForeignKey("projeto.id", ondelete="SET NULL"), nullable=True)
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class ArquivoContratosItemModel(Base):
    __tablename__ = "arquivo_contratos_item"

    id = Column(Integer, primary_key=True, index=True)
    pasta_id = Column(Integer, ForeignKey("arquivo_contratos_pasta.id", ondelete="CASCADE"), nullable=False, index=True)
    nome = Column(String(255), nullable=False)
    mime = Column(String(120), nullable=False)
    tamanho = Column(Integer, nullable=False)
    conteudo = Column(LargeBinary, nullable=False)
    origem = Column(Enum("atlas", "importado", name="arquivo_contratos_origem"), nullable=False, default="importado")
    #: O documento do kanban que gerou este arquivo; nulo no importado e no
    #: que foi apagado do kanban depois.
    documento_id = Column(
        Integer, ForeignKey("documento_contratual.id", ondelete="SET NULL"), nullable=True, index=True
    )
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now())
