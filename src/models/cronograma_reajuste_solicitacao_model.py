from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.sql import func
from src.database.database import Base


class CronogramaReajusteSolicitacaoModel(Base):
    """⭐ O **pedido de dias de ajuste** de um escopo — o único fluxo de
    aprovação que sobrou no cronograma.

    Antes esta tabela era outra coisa: o pedido para reabrir um cronograma já
    oficializado. A oficialização acabou (o cadeado trancava o calendário
    inteiro atrás de uma fila e transformava em rotina a exceção que o §5.6
    pede que seja rara), e a linha passou a carregar a única decisão que ainda
    precisa de diretoria no dia a dia: **quantos dias extras este escopo
    ganha**.

    As regras que moram no use case, não aqui:

    - **Pede o coordenador do projeto ou a diretoria de projetos, e só a
      diretoria de projetos decide.** (A diretoria pede desde 2026-08-31;
      ver `use_cases/cronograma_reajuste/solicitar.py`.)
    - **Só nos 3 primeiros dias úteis da janela**, contando a data da reunião
      inicial como dia 1. Vale a data do PEDIDO, não a da decisão — pedido no
      3º dia e aprovado no 6º continua sendo ajuste.
    - **Quantos pedidos precisar** dentro do prazo: o total ajustado é a soma
      dos aprovados (+5 e depois +5 = 10 dias ajustados).
    - Negado não fecha a porta: dentro do prazo dá para pedir de novo.

    Depois do prazo acabou — todo dia além da janela é atraso do projeto, sem
    autorização envolvida.
    """

    __tablename__ = "cronograma_reajuste_solicitacao"

    id = Column(Integer, primary_key=True, index=True)
    projeto_escopo_id = Column(Integer, ForeignKey("projeto_escopo.id"), nullable=False, index=True)
    solicitado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    #: Quantos dias úteis extras estão sendo pedidos. Aprovar SOMA este número
    #: em `projeto_escopo.dias_uteis_ajustados`.
    #:
    #: Zero nas linhas antigas, de quando a tabela pedia reabertura de
    #: cronograma e não dias — elas ficam como registro histórico.
    dias_solicitados = Column(Integer, nullable=False, default=0, server_default="0")
    motivo = Column(String(500), nullable=False)
    status = Column(
        Enum("pendente", "aprovado", "rejeitado", name="status_reajuste_cronograma"),
        nullable=False,
        default="pendente",
        server_default="pendente",
    )
    respondido_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    resposta_justificativa = Column(String(500), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    respondido_em = Column(DateTime, nullable=True)
