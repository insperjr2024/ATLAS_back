from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.sql import func
from src.database.database import Base


class BancaEntradaSolicitacaoModel(Base):
    """⭐ O **pedido pra entrar numa banca sem vaga livre pra quem pede** (2026-09-18, a pedido).

    ⚠ **Por que esta tabela existe.** A autoinscrição (`CreateCandidaturaUseCase`)
    recusa quando a banca já está no teto, ou quando a(s) última(s) vaga(s)
    está(ão) reservada(s) pro piso por frente que quem pede não cobre — e até
    aqui a recusa era o fim da linha: um erro sem saída. Aqui, como no pedido
    de exceção de choque e no de fora da janela, a pessoa que quer entrar pede
    com justificativa, e a diretoria decide depois, na aba Aprovações.

    ⭐ **Aprovar CRIA a candidatura**, acima do teto — é o próprio ponto do
    pedido: alguém de fora da composição normal entra mesmo assim, porque a
    diretoria decidiu que vale a pena, e a banca fica com mais gente que o
    máximo sem problema nenhum.

    ⚠ **Não é sobre entrar num PROJETO** (`SolicitacaoProjetoModel`, a fila de
    Vagas) — é sobre entrar como avaliador numa BANCA já marcada.
    """

    __tablename__ = "banca_entrada_solicitacao"

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    justificativa = Column(String(500), nullable=False)
    status = Column(
        Enum("pendente", "aprovada", "recusada", name="status_entrada_banca"),
        nullable=False,
        default="pendente",
        server_default="pendente",
    )
    respondido_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    resposta = Column(String(500), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    respondido_em = Column(DateTime, nullable=True)
