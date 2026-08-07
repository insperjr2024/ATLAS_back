from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from src.database.database import Base


class EntregaAlteracaoModel(Base):
    """Cada vez que uma data de entrega já registrada mudou, e por quê (§13).

    ⭐ **Marcar a entrega é livre; MUDAR uma entrega já registrada é decisão da
    diretoria.** A data que o cliente ouviu é a promessa do projeto: trocá-la em
    silêncio apagaria a diferença entre "entregamos no prazo" e "mudamos o
    prazo". Por isso a alteração pede autorização e justificativa, e fica aqui.

    Irmã de `banca_remarcacao`, e pelo mesmo motivo: a linha de origem
    (`projeto_escopo.data_entrega_real` ou `projeto.data_entrega_cliente`)
    guarda só a data que vale agora, e sem esta tabela o "de 15/09 para 22/09"
    existiria apenas na notificação já lida.

    `projeto_escopo_id` nulo = a entrega do PROJETO ao cliente
    (`projeto.data_entrega_cliente`); preenchido = a entrega daquele escopo.
    """

    __tablename__ = "entrega_alteracao"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(
        Integer, ForeignKey("projeto.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Nulo = entrega do projeto ao cliente. Preenchido = entrega de um escopo.
    projeto_escopo_id = Column(
        Integer, ForeignKey("projeto_escopo.id", ondelete="CASCADE"), nullable=True, index=True
    )
    #: Nula na primeira marcação — que não passa pelo gate, mas é registrada
    #: para o Histórico ter o "de onde veio" completo numa fonte só.
    data_anterior = Column(Date, nullable=True)
    data_nova = Column(Date, nullable=False)
    justificativa = Column(String(500), nullable=False)
    alterado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    #: Quem autorizou a mudança. Nulo na primeira marcação, que é livre.
    autorizado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
