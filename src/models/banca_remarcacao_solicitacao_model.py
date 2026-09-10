from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.sql import func

from src.database.database import Base


class BancaRemarcacaoSolicitacaoModel(Base):
    """⭐ O **pedido de remarcação** de uma banca que já tem data (§13, 2026-09-10).

    ⚠ **Por que esta tabela existe.** Remarcar uma banca dentro da janela e
    com folga era LIVRE para quem edita o projeto — bastava justificativa, e a
    data trocava na hora, sem ninguém da diretoria ver. Na prática isso fez da
    remarcação uma rotina silenciosa: o coordenador do ENSINO remarcou a banca
    e ninguém aprovou nada. Agora toda remarcação por quem não é da diretoria
    passa por aqui — mesmo desenho de `banca_fora_janela_solicitacao` e de
    `banca_excecao_choque_solicitacao`: quem conduz o projeto PEDE com
    justificativa, a diretoria DECIDE depois, na aba Aprovações.

    ⭐ **Aprovar REMARCA a banca**, não só libera (ver `DecidirRemarcacaoUseCase`):
    o pedido já carrega tudo o que a marcação precisa (escopo, data/hora,
    justificativa), então não há o que esperar de quem pediu. Se a marcação
    falhar (um choque de horário que nasceu depois, a banca tendo acontecido no
    meio tempo), o pedido VOLTA a pendente.

    ⚠ **Não confundir com `banca_fora_janela_solicitacao`.** Aquele autoriza uma
    data FORA da janela do escopo (os dias além dela viram atraso). Este é a
    remarcação em si — a data nova pode estar perfeitamente dentro da janela; o
    que se decide é se o adiamento pode acontecer, não se a janela é
    respeitada. Uma remarcação que também caia fora da janela ainda precisa dos
    dois: a diretoria aprova a remarcação aqui, e a marcação exige a
    autorização de fora da janela como sempre.

    ⚠ **`banca_id` nunca é nulo** — só se remarca o que já tem data. É a
    diferença para os outros dois pedidos, que podem nascer na primeira
    marcação.
    """

    __tablename__ = "banca_remarcacao_solicitacao"

    id = Column(Integer, primary_key=True, index=True)
    #: A banca que se quer remarcar. Sempre existe — remarcação pressupõe data.
    banca_id = Column(
        Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: O escopo pelo qual o pedido entrou (a URL da chamada que remarcou). A
    #: banca pode cobrir mais de um; é por este que a marcação vai rodar.
    projeto_escopo_id = Column(
        Integer, ForeignKey("projeto_escopo.id"), nullable=False, index=True
    )
    #: A data que vale hoje, guardada no pedido para o card mostrar "de → para"
    #: sem ter de reconstruir a partir da banca (que pode mudar no meio tempo).
    data_hora_anterior = Column(DateTime, nullable=False)
    data_hora_pretendida = Column(DateTime, nullable=False, index=True)
    justificativa = Column(String(500), nullable=False)
    status = Column(
        Enum("pendente", "aprovada", "recusada", name="status_remarcacao_banca"),
        nullable=False,
        default="pendente",
        server_default="pendente",
    )
    solicitado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    respondido_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    resposta = Column(String(500), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    respondido_em = Column(DateTime, nullable=True)
