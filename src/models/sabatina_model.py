"""Sabatina: o processo eleitoral da Insper Jr dentro do ATLAS (2026-10-05).

Uma ELEIÇÃO é um formulário que a diretoria monta ("Diretoria de Projetos",
por exemplo), com os candidatos escolhidos entre os membros e um percentual
de aprovação. Enquanto está em rascunho só a diretoria vê; ao ABRIR, todo
membro ativo que não é candidato recebe a cédula e vota uma vez (num
candidato ou em branco); ao FECHAR, a apuração sai na hora.

Voto ponderado por posição (`sabatina_peso`): consultor 1, lideranças 2,
diretoria 3 por padrão, editável. Quem acumula `cargo_extra` vota com o
maior dos dois pesos. O peso é copiado pro voto no momento em que ele é
dado, então mudar a tabela depois não reescreve eleição passada.

Quem não votou faltou à sabatina: aparece nas pendências e não entra na
conta. O percentual de aprovação é sobre os votos dados (brancos incluídos).
"""

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func
from src.database.database import Base


class SabatinaPesoModel(Base):
    """Peso do voto de cada posição. Uma linha por posição do catálogo
    (`posicao_permissao`); posição sem linha usa o padrão de
    `utils/sabatina_apuracao.peso_padrao`."""

    __tablename__ = "sabatina_peso"

    id = Column(Integer, primary_key=True, index=True)
    posicao = Column(
        String(50), ForeignKey("posicao_permissao.posicao", ondelete="CASCADE"), nullable=False, unique=True
    )
    peso = Column(Integer, nullable=False, default=1, server_default="1")


class SabatinaEleicaoModel(Base):
    """Um formulário de eleição. `rascunho` -> `aberta` -> `fechada`, sem volta."""

    __tablename__ = "sabatina_eleicao"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    #: Eleito quem passa deste percentual dos votos ponderados dados
    #: (estritamente maior: "50% mais um"). Escolhido a cada eleição.
    percentual_aprovacao = Column(Integer, nullable=False, default=50, server_default="50")
    status = Column(
        Enum("rascunho", "aberta", "fechada", name="status_sabatina_eleicao"),
        nullable=False,
        default="rascunho",
        server_default="rascunho",
    )
    #: Quem podia votar, congelado na abertura: os membros ativos que não são
    #: candidatos. É a base de "quem faltou", e quem entra na empresa depois
    #: de aberta não vota nesta.
    eleitores_ids = Column(JSON, nullable=False, default=list, server_default="[]")
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    aberta_em = Column(DateTime, nullable=True)
    fechada_em = Column(DateTime, nullable=True)


class SabatinaCandidatoModel(Base):
    __tablename__ = "sabatina_candidato"
    __table_args__ = (UniqueConstraint("eleicao_id", "usuario_id", name="uq_sabatina_candidato"),)

    id = Column(Integer, primary_key=True, index=True)
    eleicao_id = Column(
        Integer, ForeignKey("sabatina_eleicao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    ordem = Column(Integer, nullable=False, default=0, server_default="0")


class SabatinaVotoModel(Base):
    """Um voto. `candidato_id` nulo é voto em branco. Um por eleitor por eleição."""

    __tablename__ = "sabatina_voto"
    __table_args__ = (UniqueConstraint("eleicao_id", "eleitor_id", name="uq_sabatina_voto_eleitor"),)

    id = Column(Integer, primary_key=True, index=True)
    eleicao_id = Column(
        Integer, ForeignKey("sabatina_eleicao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    eleitor_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    candidato_id = Column(
        Integer, ForeignKey("sabatina_candidato.id", ondelete="CASCADE"), nullable=True, index=True
    )
    #: A posição e o peso de quem votou, NA HORA do voto.
    posicao = Column(String(50), nullable=False)
    peso = Column(Integer, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
