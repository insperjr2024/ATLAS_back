from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.sql import func
from src.database.database import Base


class CronogramaEtapaModel(Base):
    """Um trecho da execução de um escopo, pintado no calendário (§6.4).

    ⭐ **Gravada por INTERVALO, não uma linha por dia.** Quatro razões, porque
    a tentação de materializar dia a dia é real:

    1. A etapa é a entidade; o dia é uma projeção. O §6.4 diz que a pintura é
       só a visualização e que os dados estruturados são datas e duração. Uma
       linha por dia faria `nome`, `cor` e `status` não terem onde morar.
    2. O arrasto tem que ser UMA requisição. Uma etapa de 3 semanas seriam 21
       linhas; com intervalo é um PUT de dois campos, idempotente.
    3. Dia não útil corromperia a tabela por dia: os cinzas são derivados de
       `dia_nao_letivo`, que a diretoria pode RECARREGAR no meio do semestre.
       Materializado, um calendário corrigido depois deixaria linhas velhas.
    4. `contar_dias_uteis(inicio, fim, …)` já é aritmética de intervalo.

    Etapa não contígua ("roda seg–qua e volta semana que vem") são DUAS
    etapas com o mesmo nome e cor — e isso é semanticamente correto, porque o
    vão entre elas é justamente a pausa que o briefing quer visível.
    """

    __tablename__ = "cronograma_etapa"

    id = Column(Integer, primary_key=True, index=True)
    projeto_escopo_id = Column(
        Integer, ForeignKey("projeto_escopo.id"), nullable=False, index=True
    )
    nome = Column(String(100), nullable=False)
    #: `#RRGGBB`, persistida — o PNG exportado em agosto tem que continuar
    #: batendo com a legenda de agosto, mesmo que uma etapa anterior suma.
    cor = Column(String(7), nullable=False)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    status = Column(
        Enum("planejada", "em_andamento", "concluida", "cancelada", name="status_cronograma_etapa"),
        nullable=False,
        default="planejada",
        server_default="planejada",
    )
    #: Ordem na legenda e desempate de sobreposição (duas etapas no mesmo dia).
    ordem = Column(SmallInteger, nullable=False, default=0, server_default="0")
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())


class CronogramaMarcoModel(Base):
    """Os marcos pontuais do calendário (§6.4).

    ⚠ **Só dois tipos, de propósito.** ★ banca, ● entrega e 🏁 kickoff NÃO
    são regravados aqui — o calendário os desenha lendo `banca.data_hora`,
    `projeto_escopo.data_entrega_*` e `projeto.data_kickoff`. Gravar de novo
    criaria uma segunda fonte da verdade e o "uma data só" do §8 morreria no
    primeiro reagendamento.
    """

    __tablename__ = "cronograma_marco"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    #: Opcional: um marco pode ser do projeto inteiro (uma visita não presa a
    #: escopo) ou estreitado a um escopo.
    projeto_escopo_id = Column(
        Integer, ForeignKey("projeto_escopo.id"), nullable=True, index=True
    )
    tipo = Column(
        Enum("reuniao_alinhamento", "visita_presencial", name="tipo_cronograma_marco"),
        nullable=False,
    )
    data = Column(Date, nullable=False)
    nota = Column(String(150), nullable=True)
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
