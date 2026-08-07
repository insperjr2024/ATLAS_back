from sqlalchemy import Column, Date, Enum, ForeignKey, Integer, String
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

    ⭐ **A janela do escopo.** Três números que nunca se misturam:

        vendidos (imutável) · ajustados (autorizados) · atraso (derivado)

    A janela vai da reunião inicial até *vendidos + ajustados* dias úteis
    depois dela, e é dentro dela que etapas e banca devem caber. O atraso não
    tem coluna: é consequência, nunca permissão — ver `utils/janela_escopo.py`.
    """

    __tablename__ = "projeto_escopo"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    escopo_id = Column(Integer, ForeignKey("escopo.id"), nullable=True, index=True)
    nome_customizado = Column(String(150), nullable=True)
    frente_id = Column(Integer, ForeignKey("frente.id"), nullable=False, index=True)
    #: ⭐ **Imutável — é o registro comercial.** O que foi vendido ao cliente
    #: nunca é sobrescrito: precisar de mais tempo soma em `dias_uteis_ajustados`,
    #: e o que passar dos dois vira atraso (derivado). Sobrescrever este número
    #: apagaria a diferença entre "vendemos 30" e "vendemos 20 e estouramos".
    dias_uteis_vendidos = Column(Integer, nullable=False)
    #: Dias extras autorizados pela diretoria, nos 3 primeiros dias úteis da
    #: janela. Só cresce, e é a soma de todos os pedidos aprovados.
    dias_uteis_ajustados = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(
        Enum("nao_iniciado", "em_andamento", "entregue", "cancelado", name="status_projeto_escopo"),
        nullable=False,
        default="nao_iniciado",
        server_default="nao_iniciado",
    )
    #: ⭐ A data da reunião inicial. É o que **abre a janela do escopo** e faz a
    #: contagem correr; sem ela o escopo não tem janela, não consome dias e não
    #: pode ter banca marcada. Derivada das reuniões, nunca digitada — ver
    #: `sincronizar_inicio_do_escopo`.
    data_inicio = Column(Date, nullable=True)
    data_entrega_planejada = Column(Date, nullable=True)
    # Preenchê-la congela a contagem — trava do §5.5 mora no use case de entrega.
    data_entrega_real = Column(Date, nullable=True)
    tipo_atraso_entrega = Column(
        Enum("interno", "externo", name="tipo_atraso_entrega_escopo"), nullable=True
    )
