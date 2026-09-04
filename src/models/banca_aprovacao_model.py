from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Boolean
from sqlalchemy.sql import func
from src.database.database import Base


class BancaAprovacaoModel(Base):
    """⭐ A decisão de quem aprova a banca (§5.5, §8) — não é mais o voto dos
    avaliadores, é a assinatura de diretoria de projetos + gerente da(s)
    frente(s) da banca.

    Uma linha por decisão: `papel="diretoria"` tem `frente_id` nulo (é uma
    assinatura só, para a banca inteira); `papel="gerente"` tem uma linha POR
    FRENTE da banca (`banca_frente`) — banca de projeto sinérgico com duas
    frentes precisa de uma linha de cada gerente.

    ⚠ **Sem UNIQUE em (banca_id, papel, frente_id).** Responder de novo não
    enfileira uma segunda decisão: o use case (`RegistrarAprovacaoBancaUseCase`)
    busca a linha existente e atualiza — mesmo padrão de "pedido pendente
    atualiza o que já está lá" de `BancaExcecaoChoqueModel`.
    """

    __tablename__ = "banca_aprovacao"

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False, index=True)
    papel = Column(Enum("diretoria", "gerente", name="papel_aprovacao_banca"), nullable=False)
    #: Nulo para `papel="diretoria"` (assinatura única da banca); obrigatório
    #: para `papel="gerente"` (uma assinatura por frente da banca).
    frente_id = Column(Integer, ForeignKey("frente.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    aprovado = Column(Boolean, nullable=False)
    nota = Column(String(500), nullable=True)
    #: ⭐ Em QUAL tentativa da banca (§9) esta assinatura vale — mesmo motivo
    #: de `avaliacao.sessao`: `banca_id` é o mesmo nas duas tentativas, e sem
    #: isto uma assinatura dada na 1ª banca (antes de uma remarcação) contaria
    #: como válida para a 2ª, que ninguém revisou de novo.
    sessao = Column(Integer, nullable=False, default=1, server_default="1")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
