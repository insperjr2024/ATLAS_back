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
    #: Os responsáveis vivem em `tarefa_responsavel` (N:N) desde 2026-09-02.
    #: Antes era um `responsavel_id` NOT NULL aqui; virou lista porque uma
    #: tarefa pode ser de várias pessoas ou de todos os consultores do
    #: projeto. Uma tarefa sempre tem AO MENOS um responsável, garantido no
    #: use case, não por constraint.
    prazo = Column(Date, nullable=False)
    #: Substituiu o ENUM `status`: a coluna do kanban é dado, não código.
    coluna_id = Column(Integer, ForeignKey("tarefa_coluna.id"), nullable=False, index=True)
    # Nullable pelo mesmo motivo de `projeto.criado_por`: apagar de vez quem
    # criou a tarefa (usuário desligado) não pode levar a tarefa junto. A
    # tarefa só some com a pessoa quando ela era a ÚLTIMA responsável (ver
    # `delete_usuario_permanente`).
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    #: Só é tocado quando o STATUS muda, não em qualquer PATCH — é o que
    #: alimenta a "última movimentação" do §7.2.
    movida_em = Column(DateTime, nullable=False, server_default=func.now())


class TarefaResponsavelModel(Base):
    """Quem responde por uma tarefa. Um ou vários por tarefa.

    Substituiu a coluna `tarefa.responsavel_id` (2026-09-02): uma tarefa pode
    ser de várias pessoas, ou de todos os consultores do projeto. É um
    SNAPSHOT: quem entra no projeto depois não vira responsável de tarefa
    antiga sozinho.

    `tarefa_id` tem `ondelete=CASCADE` porque a linha só existe enquanto a
    tarefa existe. `usuario_id` não: apagar um usuário de vez é tratado à mão
    em `delete_usuario_permanente`, que decide se a tarefa sobrevive.
    """

    __tablename__ = "tarefa_responsavel"
    __table_args__ = (
        UniqueConstraint("tarefa_id", "usuario_id", name="uq_tarefa_responsavel"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tarefa_id = Column(
        Integer, ForeignKey("tarefa.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)


class ReuniaoSemanalModel(Base):
    """O registro de que a reunião semanal aconteceu (§6.4).

    🧮 **"Projeto sem reunião na semana" é AUSÊNCIA DE LINHA** na janela
    seg–dom — não um campo. Mais de uma reunião na mesma semana = mais linhas,
    que é exatamente o que o briefing permite.

    ⭐ **É daqui que sai `projeto_escopo.data_inicio`** (§5.4): a reunião diz
    sobre QUAL escopo foi, e a primeira reunião de um escopo é a "reunião
    inicial" que abre a janela dele e faz a contagem começar a correr.

    Dois tipos na mesma tabela, distinguidos por `projeto_escopo_id`:

    - **reunião inicial** (escopo preenchido) — abre a janela do escopo;
    - **reunião geral** (escopo nulo) — a semanal do projeto, que não mexe em
      contagem nenhuma e aceita observações em texto livre.

    ⚠ O UNIQUE inclui o escopo porque as duas passaram a ser marcadas no MESMO
    calendário do cronograma: sem ele, marcar a reunião inicial de um escopo no
    dia em que já houve a reunião geral estouraria. O MySQL não cobre NULL no
    índice, então "uma reunião geral por dia" é validado no use case.
    """

    __tablename__ = "reuniao_semanal"
    __table_args__ = (
        UniqueConstraint(
            "projeto_id", "data_reuniao", "projeto_escopo_id", name="uq_reuniao_projeto_data"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    #: Sobre qual escopo foi a reunião. Vazio = reunião geral do projeto, que
    #: não inicia contagem nenhuma.
    projeto_escopo_id = Column(
        Integer, ForeignKey("projeto_escopo.id"), nullable=True, index=True
    )
    data_reuniao = Column(Date, nullable=False, index=True)
    #: O que foi conversado — texto livre, sem estrutura de propósito: é a ata
    #: informal da reunião geral, e forçar campos aqui faria ninguém preencher.
    observacoes = Column(String(500), nullable=True)
    # Nullable pelo mesmo motivo: quem registrou pode ser excluído de vez sem
    # apagar o registro de que a reunião aconteceu — a data em si é o que o
    # §5.4 usa (`data_inicio` do escopo), não quem digitou.
    registrado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
