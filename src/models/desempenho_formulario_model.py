from sqlalchemy import Boolean, Column, DateTime, Enum, Index, Integer, String, Text, text
from src.database.database import Base


class DesempenhoFormularioModel(Base):
    """Formulário de uma combinação (tipo, papel). Há UM vigente por
    combinação (índice único parcial em `vigente`); editar é atualizar essa
    linha e suas seções/critérios.

    Versão congelada (2026-10-06, a pedido): ao editar com lote aberto e
    escolher "só pra futuros", a linha de então vira `vigente = False` e fica
    amarrada aos lotes abertos por `desempenho_lote_formulario`; uma linha
    nova, já editada, passa a ser a vigente. As respostas já dadas continuam
    apontando pros critérios da versão congelada, e quem ainda vai responder
    naquele lote responde a mesma versão.

    ⭐ `papel="escopo"` (2026-09-09) é o caso fora da curva: não é um papel de
    pessoa, é o formulário "Avaliação do Escopo" — auto-avaliação que cada
    participante do projeto responde uma vez na rodada de finalização. Só
    existe como `(finalizacao, escopo)`.
    """

    __tablename__ = "desempenho_formulario"
    __table_args__ = (
        Index(
            "uq_desempenho_formulario_vigente",
            "tipo",
            "papel",
            unique=True,
            postgresql_where=text("vigente"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(Enum("periodico", "finalizacao", name="desempenho_formulario_tipo"), nullable=False)
    papel = Column(
        Enum("consultor", "coordenador", "escopo", name="desempenho_formulario_papel"),
        nullable=False,
    )
    nota_geral_titulo = Column(String(200), nullable=False)
    nota_geral_descricao = Column(Text, nullable=False)
    comentarios_titulo = Column(String(200), nullable=False)
    comentarios_descricao = Column(Text, nullable=False)
    comentarios_aviso = Column(Text, nullable=False)
    vigente = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    #: Quando deixou de ser a vigente (virou versão congelada de lotes abertos).
    congelado_em = Column(DateTime, nullable=True)
