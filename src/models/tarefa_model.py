from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func
from src.database.database import Base


class TarefaModel(Base):
    """Uma tarefa do projeto, no kanban (§4, §6.4).

    🧮 **"Vencida" NÃO é campo.** É `prazo` passado e a tarefa ainda aberta,
    calculado em `utils/tarefa_status.py` na hora de servir. Gravar um
    booleano exigiria um job para virá-lo à meia-noite, e ele ficaria errado
    entre uma passada e outra.

    "Ainda aberta" hoje vem de `tarefa_coluna.encerra_tarefa`, não de uma
    lista fixa de status — as colunas são configuráveis pela diretoria.
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
    #: Substituiu o ENUM `status`: a coluna do kanban é dado, não código.
    coluna_id = Column(Integer, ForeignKey("tarefa_coluna.id"), nullable=False, index=True)
    # Nullable pelo mesmo motivo de `projeto.criado_por`: apagar de vez quem
    # criou a tarefa (usuário desligado) não pode levar a tarefa junto — só
    # quem é RESPONSÁVEL (`responsavel_id`, continua NOT NULL) é dono dela de
    # verdade o bastante pra a tarefa sumir com a pessoa.
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    #: Só é tocado quando o STATUS muda, não em qualquer PATCH — é o que
    #: alimenta a "última movimentação" do §7.2.
    movida_em = Column(DateTime, nullable=False, server_default=func.now())


class ReuniaoSemanalModel(Base):
    """O registro de que a reunião semanal aconteceu (§6.4).

    🧮 **"Projeto sem reunião na semana" é AUSÊNCIA DE LINHA** na janela
    seg–dom — não um campo. Mais de uma reunião na mesma semana = mais linhas,
    que é exatamente o que o briefing permite.

    ⭐ **É daqui que sai `projeto_escopo.data_inicio`** (§5.4): a reunião diz
    sobre QUAL escopo foi, e a primeira reunião de um escopo é a "reunião
    inicial" que faz a contagem dele começar a correr.
    """

    __tablename__ = "reuniao_semanal"
    __table_args__ = (
        UniqueConstraint("projeto_id", "data_reuniao", name="uq_reuniao_projeto_data"),
    )

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    #: Sobre qual escopo foi a reunião. Vazio = reunião geral do projeto, que
    #: não inicia contagem nenhuma.
    projeto_escopo_id = Column(
        Integer, ForeignKey("projeto_escopo.id"), nullable=True, index=True
    )
    data_reuniao = Column(Date, nullable=False, index=True)
    # Nullable pelo mesmo motivo: quem registrou pode ser excluído de vez sem
    # apagar o registro de que a reunião aconteceu — a data em si é o que o
    # §5.4 usa (`data_inicio` do escopo), não quem digitou.
    registrado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
