from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String
from src.database.database import Base


class ProjetoEscopoModel(Base):
    """O escopo vendido dentro de um projeto (F4, §4/§5.1/§5.4).

    Não é o catálogo (`escopo`) — é a linha que amarra um tipo de trabalho (ou
    um "Outro" digitado) a UM projeto, com os dias úteis vendidos e as datas
    que alimentam `utils/contagem_dias.py`.

    "Outro": `escopo_id` nulo + `nome_customizado` preenchido. Validado no use
    case (exatamente um dos dois), não em CHECK — o MySQL da stack não impõe.

    Sem UNIQUE em (projeto_id, escopo_id): o mesmo escopo de catálogo pode
    legitimamente aparecer duas vezes num projeto grande.
    """

    __tablename__ = "projeto_escopo"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    escopo_id = Column(Integer, ForeignKey("escopo.id"), nullable=True, index=True)
    nome_customizado = Column(String(150), nullable=True)
    frente_id = Column(Integer, ForeignKey("frente.id"), nullable=False, index=True)
    dias_uteis_vendidos = Column(Integer, nullable=False)
    # Ordem de exibição na tela do projeto — não é o `id` (que é ordem de
    # criação, e reordenar não deveria recriar linha). Default 0 pra quem já
    # existia antes deste campo: com todo mundo empatado, o desempate por
    # `id` mantém a ordem de sempre sem precisar de backfill.
    ordem = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(
        Enum("nao_iniciado", "em_andamento", "entregue", "cancelado", name="status_projeto_escopo"),
        nullable=False,
        default="nao_iniciado",
        server_default="nao_iniciado",
    )
    # ⭐ a contagem do §5.4 só corre com isto preenchido.
    data_inicio = Column(Date, nullable=True)
    # Carimbo informativo do §5.3 — não trava mais edição do cronograma
    # (2026-08-06: o fluxo de reajuste que fazia isso foi removido).
    cronograma_oficializado_em = Column(DateTime, nullable=True)
    data_entrega_planejada = Column(Date, nullable=True)
    # Preenchê-la congela a contagem — trava do §5.5 mora no use case de entrega.
    data_entrega_real = Column(Date, nullable=True)
    tipo_atraso_entrega = Column(
        Enum("interno", "externo", name="tipo_atraso_entrega_escopo"), nullable=True
    )
