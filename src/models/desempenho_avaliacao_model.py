from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Text, func
from src.database.database import Base


class DesempenhoAvaliacaoModel(Base):
    """Uma avaliação de desempenho: `avaliador_id` avaliou `avaliado_id` dentro
    de um lote. A unicidade por (lote, avaliador, avaliado) garante que o
    mesmo par não preenche duas vezes no mesmo lote, mesmo que compartilhem
    mais de um projeto (regra 2.3) — diferente da avaliação de banca, aqui não
    existe uma linha por projeto em comum.

    2026-10-05: a Avaliação do Escopo (avaliador == avaliado) passou a ser
    uma resposta POR ESCOPO, então `projeto_escopo_id` entrou na chave. Vai
    como `coalesce(.., 0)` no índice porque, no Postgres, NULL nunca é igual
    a NULL num UNIQUE, e a avaliação entre pessoas (escopo nulo) perderia a
    trava de duplicidade.
    """

    __tablename__ = "desempenho_avaliacao"

    id = Column(Integer, primary_key=True, index=True)
    lote_id = Column(Integer, ForeignKey("desempenho_lote.id"), nullable=False, index=True)
    formulario_id = Column(Integer, ForeignKey("desempenho_formulario.id"), nullable=False)
    avaliador_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    avaliado_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    #: Só na Avaliação do Escopo: QUAL escopo vendido a pessoa avaliou.
    #: Nulo na avaliação entre pessoas e nas Avaliações do Escopo anteriores a
    #: 2026-10-05 (uma por pessoa por lote, escopo resolvido depois pela
    #: frente, ver `get_avaliacao.py`).
    projeto_escopo_id = Column(
        Integer, ForeignKey("projeto_escopo.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nota_geral = Column(Integer, nullable=False)
    comentarios = Column(Text, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index(
            "uq_desempenho_avaliacao_par",
            lote_id,
            avaliador_id,
            avaliado_id,
            func.coalesce(projeto_escopo_id, 0),
            unique=True,
        ),
    )
