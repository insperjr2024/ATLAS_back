from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.sql import func
from src.database.database import Base


class BancaExcecaoChoqueModel(Base):
    """⭐ O **pedido de exceção** para marcar uma banca num horário já ocupado (§8).

    ⚠ **Por que esta tabela existe.** O §8 bloqueia duas bancas no mesmo
    horário e diz que a exceção é da diretoria — mas até aqui não havia como
    pedi-la. Quem esbarrava no choque recebia *"a exceção só é liberada pela
    diretoria"* e nenhuma saída: nem um botão, nem uma tela; nem sendo diretor,
    porque a rota que gravava a liberação não tinha chamador nenhum no front. A
    regra existia e o caminho para cumpri-la, não.

    ⭐ **A exceção é do PAR (escopo + horário), não da banca.**
    O mecanismo anterior gravava `excecao_choque_por` na banca **já existente** —
    a "outra" — e a partir dali aquele horário virava passe livre: qualquer
    banca futura marcada ali passava sem ninguém decidir nada, porque
    `_checar_choque` simplesmente pulava as bancas com a flag. Uma liberação
    pontual virava um buraco permanente na regra.

    Aqui o que é aprovado é **este escopo, neste horário**. Outro escopo
    querendo o mesmo horário abre outro pedido.

    ⚠ **`banca_id` é nulo quando a banca ainda não existe.** O choque é
    detectado ANTES de criar a banca — é justamente o que impede a criação. O
    que sempre existe é o escopo, e por isso é ele a chave do pedido.

    Limitação conhecida, herdada de `_checar_choque`: a comparação é por
    `data_hora` EXATA. Bancas não têm duração gravada, então duas marcadas às
    14h e às 14h30 não são tratadas como conflito.

    As regras que moram no use case, não aqui:

    - **Quem pode marcar a banca pede; só o diretor decide.**
    - Um pedido pendente por (escopo, horário) — pedir de novo não enfileira
      duplicata, atualiza o que já está lá.
    - Recusado não fecha a porta: dá para pedir de novo com outro argumento.
    """

    __tablename__ = "banca_excecao_choque_solicitacao"

    id = Column(Integer, primary_key=True, index=True)
    #: O escopo cuja banca quer o horário. A chave real do pedido — existe
    #: mesmo quando a banca ainda não foi criada.
    projeto_escopo_id = Column(Integer, ForeignKey("projeto_escopo.id"), nullable=False, index=True)
    #: Nulo enquanto a banca não existe (choque detectado na criação).
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="SET NULL"), nullable=True, index=True)
    data_hora_pretendida = Column(DateTime, nullable=False, index=True)
    #: A banca que já ocupa o horário — guardada para a diretoria decidir com o
    #: contexto na tela ("choca com a banca do projeto X"), sem ter de procurar.
    banca_conflitante_id = Column(Integer, ForeignKey("banca.id", ondelete="SET NULL"), nullable=True)
    justificativa = Column(String(500), nullable=False)
    status = Column(
        Enum("pendente", "aprovada", "recusada", name="status_excecao_choque"),
        nullable=False,
        default="pendente",
        server_default="pendente",
    )
    solicitado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    respondido_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    resposta = Column(String(500), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    respondido_em = Column(DateTime, nullable=True)
