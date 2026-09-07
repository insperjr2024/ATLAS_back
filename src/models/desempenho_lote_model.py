from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.sql import func
from src.database.database import Base


class DesempenhoLoteModel(Base):
    """Uma rodada de avaliação de desempenho (periódica ou de finalização).

    `override_manual` é tri-state, não booleano: `NULL` = segue
    `data_inicio`/`data_fim` (calculado, nunca gravado); `"aberto"`/`"fechado"`
    = força, ignorando as datas até alguém voltar pro automático.
    """

    __tablename__ = "desempenho_lote"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    tipo = Column(Enum("periodico", "finalizacao", name="desempenho_lote_tipo"), nullable=False)
    data_inicio = Column(DateTime, nullable=False)
    data_fim = Column(DateTime, nullable=False)
    override_manual = Column(Enum("aberto", "fechado", name="desempenho_lote_override"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    #: ⭐ De onde este lote veio, quando veio de uma banca (2026-09-05). Nulo
    #: em toda periódica e em toda finalização aberta à mão — só a
    #: automática (`FinalizacaoAutomaticaBancaUseCase`) preenche. É o que
    #: permite `CancelarBancaUseCase` desfazer o lote certo, e só o certo,
    #: quando alguém cancela a banca DEPOIS dela já ter sido marcada
    #: realizada (imprevisto de última hora).
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="SET NULL"), nullable=True)
