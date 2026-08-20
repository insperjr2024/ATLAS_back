from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.sql import func
from src.database.database import Base


class BancaForaJanelaSolicitacaoModel(Base):
    """⭐ O **pedido de autorização** para marcar uma banca fora da janela do
    escopo (§13).

    ⚠ **Por que esta tabela existe.** Antes, marcar fora da janela era um
    atalho de um ato só: só quem tinha `posicao == "diretor"` conseguia
    fazer, e fazia sozinho, na mesma chamada que gravava a banca — pedido e
    decisão eram a mesma pessoa no mesmo clique. Aqui, como no pedido de
    exceção de choque (`banca_excecao_choque_solicitacao`) e no pedido de
    dias de ajuste, são dois atos separados: quem marca pede com
    justificativa, a diretoria decide depois, na aba Aprovações.

    ⚠ **Não confundir com `cronograma_reajuste_solicitacao`.** Aquele pedido
    faz `dias_uteis_ajustados` CRESCER — a janela do escopo inteiro se move,
    e só cabe nos 3 primeiros dias úteis dela (§8). Este pedido autoriza só
    UMA marcação de banca específica (este escopo, esta data); a janela do
    escopo não muda, e os dias além dela continuam contando como atraso do
    projeto (§13) mesmo depois de aprovado — é uma autorização, não uma
    prorrogação.

    ⭐ **A autorização é do PAR (escopo + data/hora pretendida)**, mesmo
    desenho de `banca_excecao_choque_solicitacao`: aprovar libera aquele
    escopo para aquela data específica, não o escopo para sempre.

    ⚠ **`banca_id` é nulo quando a banca ainda não existe** — o pedido pode
    nascer na primeira marcação, antes de haver linha em `banca`.
    """

    __tablename__ = "banca_fora_janela_solicitacao"

    id = Column(Integer, primary_key=True, index=True)
    #: O escopo cuja banca quer a data. A chave real do pedido — existe mesmo
    #: quando a banca ainda não foi criada.
    projeto_escopo_id = Column(Integer, ForeignKey("projeto_escopo.id"), nullable=False, index=True)
    #: Nulo enquanto a banca não existe (o gate roda antes de criá-la).
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="SET NULL"), nullable=True, index=True)
    data_hora_pretendida = Column(DateTime, nullable=False, index=True)
    justificativa = Column(String(500), nullable=False)
    status = Column(
        Enum("pendente", "aprovada", "recusada", name="status_fora_janela"),
        nullable=False,
        default="pendente",
        server_default="pendente",
    )
    solicitado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    respondido_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    resposta = Column(String(500), nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    respondido_em = Column(DateTime, nullable=True)
