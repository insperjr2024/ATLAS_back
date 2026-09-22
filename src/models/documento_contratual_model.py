from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text

from src.database.database import Base


class DocumentoContratualModel(Base):
    """Um documento jurídico em andamento dentro de um PROJETO do ATLAS —
    Contrato de Prestação de Serviços, TEP, NDA, Termo de Uso de Imagem ou
    Termo Aditivo (ver `utils/status_documento_contratual.py`).

    ⭐ 2026-09-16 — nasce da integração com a antiga plataforma Contratos
    (`contratos-backend`), separada até aqui. Lá isto era `ContratoModel`,
    dependurado numa "pasta de cliente" própria (`ProjetoModel` da Contratos);
    aqui pendura direto no `ProjetoModel` do ATLAS — a pasta separada deixou
    de existir, um projeto ATLAS agora É a pasta.

    É aqui que mora o workflow (status + dados preenchidos). Cada documento de
    um projeto corre de forma independente: o NDA pode estar em revisão
    interna enquanto o Contrato de Prestação aguarda o cliente.

    Não confundir com `DocumentoContratualVersaoModel`, que é o ARQUIVO gerado
    (uma linha por versão de .docx/.pdf). Um documento jurídico tem N versões
    ao longo das revisões.
    """

    __tablename__ = "documento_contratual"
    # Um documento de cada tipo por projeto: uma revisão gera nova VERSÃO
    # (DocumentoContratualVersaoModel), não um novo documento jurídico.
    #
    # Postgres não aceita `WHERE` numa UNIQUE CONSTRAINT — só num ÍNDICE
    # único, daí `Index` em vez de `UniqueConstraint` aqui. A condição é
    # redundante na prática (dois NULLs já contam como distintos pro
    # Postgres), mas deixa a intenção explícita: a regra "um documento de
    # cada tipo por projeto" só existe pra quem TEM projeto — institucional
    # (`projeto_id` nulo) pode ter quantos quiser do mesmo tipo.
    __table_args__ = (
        Index(
            "uq_documento_contratual_projeto_tipo",
            "projeto_id",
            "tipo",
            unique=True,
            postgresql_where=text("projeto_id IS NOT NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    #: ⭐ 2026-09-21 — nullable: contrato institucional (Agro etc.) não tem
    #: projeto de entrega nenhum por trás — não faz sentido poluir a tabela
    #: `projeto` só pra pendurar um documento jurídico avulso. Quando NULO,
    #: `nome_projeto_externo`/`cliente_externo` (abaixo) é que identificam o
    #: documento nas telas — ver `criar_documento_institucional.py`.
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=True, index=True)
    #: Só preenchidos quando `projeto_id` é nulo — o nome/cliente digitados
    #: como TEXTO no formulário do documento, não um cadastro de projeto.
    nome_projeto_externo = Column(String(150), nullable=True)
    cliente_externo = Column(String(150), nullable=True)
    #: contrato | tep | nda | uso_imagem | aditivo | outro — ver
    #: `utils/status_documento_contratual.py`.
    tipo = Column(String(20), nullable=False)
    status = Column(String(40), nullable=False, default="aguardando_preenchimento")
    #: Blob JSON com os dados do formulário. O shape depende do `tipo` — ver o
    #: gerador correspondente em `src/documentos_contratuais/`.
    dados = Column(JSON, nullable=True)
    #: Quem preencheu (venda, Diretora de Projetos etc.) confirma
    #: explicitamente antes de o documento seguir pro Jurídico — dá uma
    #: chance de corrigir um dado errado ou cancelar um pedido feito por
    #: engano antes do envio. Antes de confirmado: só quem preencheu
    #: edita/cancela. Depois: só quem tem `pode_editar_documento_juridico`.
    #: Só importa enquanto o status é "aguardando_preenchimento".
    confirmado = Column(Boolean, nullable=False, default=False)
    #: Preenchido no arquivamento, calculado pela data em que ESTE documento
    #: foi assinado — dois documentos do mesmo projeto podem ter gestões
    #: diferentes.
    gestao_id = Column(Integer, ForeignKey("semestre.id"), nullable=True)
    criado_em = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())

    projeto = relationship("ProjetoModel")
    versoes = relationship(
        "DocumentoContratualVersaoModel", back_populates="documento", cascade="all, delete-orphan"
    )
    tokens = relationship(
        "TokenAprovacaoContratualModel", back_populates="documento", cascade="all, delete-orphan"
    )
    solicitacoes = relationship(
        "SolicitacaoAlteracaoContratualModel", back_populates="documento", cascade="all, delete-orphan"
    )
