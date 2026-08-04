from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func
from src.database.database import Base


class TarefaModel(Base):
    """Uma tarefa do projeto, no kanban de 5 colunas (§4, §6.4).

    🧮 **"Vencida" NÃO é campo.** É `prazo` passado e status fora de
    {concluido, cancelado}, calculado em `utils/tarefa_status.py` na hora de
    servir. Gravar um booleano exigiria um job para virá-lo à meia-noite, e
    ele ficaria errado entre uma passada e outra.
    """

    __tablename__ = "tarefa"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    #: Opcional: a que escopo a tarefa pertence. Nem toda tarefa é de escopo.
    projeto_escopo_id = Column(
        Integer, ForeignKey("projeto_escopo.id"), nullable=True, index=True
    )
    titulo = Column(String(200), nullable=False)
    responsavel_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    prazo = Column(Date, nullable=False)
    status = Column(
        Enum(
            "a_fazer", "em_andamento", "validacao", "concluido", "cancelado", name="status_tarefa"
        ),
        nullable=False,
        default="a_fazer",
        server_default="a_fazer",
    )
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    #: Só é tocado quando o STATUS muda, não em qualquer PATCH — é o que
    #: alimenta a "última movimentação" do §7.2.
    movida_em = Column(DateTime, nullable=False, server_default=func.now())


class ReuniaoSemanalModel(Base):
    """O registro de que a reunião semanal aconteceu (§6.4).

    🧮 **"Projeto sem reunião na semana" é AUSÊNCIA DE LINHA** na janela
    seg–dom — não um campo. Mais de uma reunião na mesma semana = mais linhas,
    que é exatamente o que o briefing permite.
    """

    __tablename__ = "reuniao_semanal"
    __table_args__ = (
        UniqueConstraint("projeto_id", "data_reuniao", name="uq_reuniao_projeto_data"),
    )

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    data_reuniao = Column(Date, nullable=False, index=True)
    registrado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
