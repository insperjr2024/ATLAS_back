from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from src.database.database import Base


class TarefaColunaModel(Base):
    """As colunas do kanban — **de cada projeto**, configuráveis pela diretoria.

    Eram um ENUM de 5 valores cravado no banco, depois viraram uma
    configuração global. Agora pertencem ao projeto: cada um tem o seu fluxo,
    e mexer no board de um não mexe no dos outros.

    Todo projeto nasce com o conjunto padrão (`COLUNAS_PADRAO` em
    `use_cases/tarefa/colunas.py`), senão o kanban abriria sem nenhuma coluna
    e não haveria onde a primeira tarefa cair.

    ⭐ **`encerra_tarefa` é o campo que segura a regra de negócio.** "Vencida"
    não é campo: é prazo passado + tarefa ainda aberta. Com o ENUM, "aberta"
    era `status not in {concluido, cancelado}` — uma lista fixa no código.
    Com colunas livres, a diretoria precisa dizer, ao criar cada coluna, se
    uma tarefa que chega ali está encerrada. Sem isso, criar uma coluna
    "Arquivado" faria toda tarefa arquivada aparecer como vencida para
    sempre, e o monitoramento (§7.2) contaria trabalho que não existe.
    """

    __tablename__ = "tarefa_coluna"
    #: A chave é única DENTRO do projeto: cada projeto tem o seu "a_fazer".
    __table_args__ = (
        UniqueConstraint("projeto_id", "chave", name="uq_coluna_projeto_chave"),
    )

    #: Sem `index=True`, ao contrario dos outros models: o nome gerado
    #: (`ix_tarefa_coluna_id`) colide com o indice de `tarefa.coluna_id`,
    #: e nome de indice no Postgres e unico por schema. O indice seria
    #: redundante de qualquer forma — a PK ja cria `tarefa_coluna_pkey`
    #: sobre esta coluna. Nao reponha.
    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    #: Slug estável das colunas padrão — é por ele que a migration converteu
    #: o ENUM antigo e que a criação de projeto continua idempotente. Colunas
    #: criadas à mão pela diretoria nascem sem chave.
    chave = Column(String(30), nullable=True)
    nome = Column(String(60), nullable=False)
    #: `#RRGGBB` — a cor "cheia" (o ponto do rótulo). Os tons pálidos do
    #: fundo e do texto são derivados dela no front, para a diretoria
    #: escolher UMA cor e não quatro.
    cor = Column(String(7), nullable=False)
    ordem = Column(SmallInteger, nullable=False, default=0, server_default="0")
    #: ⭐ Tarefa nesta coluna está encerrada: não fica vencida nem conta como
    #: trabalho ativo no monitoramento.
    encerra_tarefa = Column(Boolean, nullable=False, default=False, server_default="0")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
