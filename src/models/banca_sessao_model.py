from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.sql import func

from src.database.database import Base


class BancaSessaoModel(Base):
    """⭐ Cada TENTATIVA de uma banca — a 1ª, a 2ª depois de uma reprovação…

    ⚠ **Existe porque a reprovação estava sendo apagada.** `banca` guarda o
    estado ATUAL de uma sessão só, e `MarcarBancaEscopoUseCase` limpava
    `realizado_em` e `resultado` ao remarcar uma banca já realizada — o que era
    necessário (senão o escopo seguiria com a entrega liberada por uma sessão
    que não vale mais), mas jogava fora o fato de que a banca havia sido
    REPROVADA. Sobrava a data anterior em `banca_remarcacao` e nada sobre o
    veredito.

    ⭐ **Uma banca por escopo continua valendo.** O UNIQUE de
    `banca_escopo.projeto_escopo_id` fica de pé, e com ele os ~30 pontos do
    sistema que perguntam "qual a banca deste escopo?" — trava de entrega
    (§5.5), atraso do §7.4, janela do cronograma, monitoramento. O que muda é
    que a linha de `banca` passa a ter um histórico de sessões atrás dela.

    ⚠ **Remarcar NÃO abre sessão nova.** Adiar uma banca que ainda não
    aconteceu é a MESMA tentativa em outra data — quem registra isso é
    `banca_remarcacao`. Sessão nova só nasce quando a anterior FECHOU com
    veredito e o escopo precisa de outra banca (§9). É a diferença entre
    "mudou de dia" e "aconteceu de novo".
    """

    __tablename__ = "banca_sessao"
    __table_args__ = (
        # Duas sessões nº 2 na mesma banca seriam duas "segundas bancas" — o
        # número é o que a tela mostra ("2ª banca"), então precisa ser único.
        UniqueConstraint("banca_id", "numero", name="uq_banca_sessao_numero"),
    )

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(
        Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: 1 = a primeira. É o número que a tela mostra ("2ª banca do escopo").
    numero = Column(Integer, nullable=False, default=1, server_default="1")
    #: A data que ESTA sessão teve. Copiada de `banca.data_hora` e mantida em
    #: sincronia enquanto a sessão é a corrente — depois de encerrada, congela.
    data_hora = Column(DateTime, nullable=True)
    realizado_em = Column(DateTime, nullable=True)
    resultado = Column(
        Enum("aprovada", "nao_aprovada", name="resultado_banca_sessao"), nullable=True
    )
    #: Preenchido quando a sessão dá lugar à seguinte. `None` = é a corrente.
    #: Não se deduz por `resultado`: uma sessão aprovada também está encerrada,
    #: só que sem sucessora.
    encerrada_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
