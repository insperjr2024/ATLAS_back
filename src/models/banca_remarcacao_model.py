from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from src.database.database import Base


class BancaRemarcacaoModel(Base):
    """Cada vez que a data de uma banca mudou, e por quê (§9).

    ⭐ **Remarcar nunca é silencioso.** A `banca` guarda só a data que vale
    agora; sem esta tabela, "de 06/08 para 20/08" existiria apenas na
    notificação que já foi lida e sumiu — e o Histórico do projeto não teria de
    onde reconstruir a decisão.

    ⚠ **Banca reprovada não gera banca nova.** A mesma linha de `banca` é
    remarcada, o que mantém `banca_escopo` intacto e a trava de entrega do
    §5.5 sem ambiguidade. É por isso que o histórico precisa morar aqui: a
    linha original é sobrescrita a cada remarcação.

    `autorizado_por` é nulo quando a remarcação foi livre — dentro da janela e
    com mais de 5 dias úteis de folga, o §13 não exige diretoria. Preenchido, é
    o registro de quem autorizou a exceção.
    """

    __tablename__ = "banca_remarcacao"

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(
        Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Nula quando a banca ainda não tinha data — a primeira marcação não é
    #: remarcação, mas registrá-la dá o "de onde veio" completo na aba
    #: Histórico sem juntar duas fontes.
    data_anterior = Column(DateTime, nullable=True)
    data_nova = Column(DateTime, nullable=False)
    justificativa = Column(String(500), nullable=False)
    remarcado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    #: A diretora que liberou a exceção do §13 (banca fora da janela, ou dentro
    #: dos próximos 5 dias úteis). Nulo = remarcação livre, sem gate.
    autorizado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
