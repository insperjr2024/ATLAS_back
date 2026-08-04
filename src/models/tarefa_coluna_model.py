from sqlalchemy import Boolean, Column, DateTime, Integer, SmallInteger, String
from sqlalchemy.sql import func
from src.database.database import Base


class TarefaColunaModel(Base):
    """As colunas do kanban — configuráveis pela diretoria.

    Eram um ENUM de 5 valores cravado no banco. Viraram dados porque a área
    quer montar o próprio fluxo: renomear, recolorir, reordenar e criar
    colunas novas sem migration.

    ⭐ **`encerra_tarefa` é o campo que segura a regra de negócio.** "Vencida"
    não é campo: é prazo passado + tarefa ainda aberta. Com o ENUM, "aberta"
    era `status not in {concluido, cancelado}` — uma lista fixa no código.
    Com colunas livres, a diretoria precisa dizer, ao criar cada coluna, se
    uma tarefa que chega ali está encerrada. Sem isso, criar uma coluna
    "Arquivado" faria toda tarefa arquivada aparecer como vencida para
    sempre, e o monitoramento (§7.2) contaria trabalho que não existe.
    """

    __tablename__ = "tarefa_coluna"

    id = Column(Integer, primary_key=True, index=True)
    #: Slug estável das 5 colunas originais — é por ele que a migration
    #: converteu o ENUM antigo e que o seed continua idempotente. Colunas
    #: criadas pela diretoria nascem sem chave.
    chave = Column(String(30), nullable=True, unique=True)
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
