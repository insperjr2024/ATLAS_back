"""merge_ajustes_com_main_e_repoe_reajuste

Une as duas heads que o merge de `main` em `ajustes` deixou — e desfaz o que a
reversão da main tinha tirado, porque a decisão foi **manter o fluxo de pedido
de dias de ajuste**.

⚠ Escrita à mão, não autogerada. O `--autogenerate` veria apenas "falta a
tabela `cronograma_reajuste_solicitacao`" e não teria como saber que ela
existiu, foi dropada de propósito por `72a7a5145a5a` e agora volta com uma
coluna a mais (`dias_solicitados`, que nasceu depois na outra branch).

São quatro coisas, e cada uma existe por um motivo diferente:

1. **Une as heads** `a7c31d0b9e58` (ponta da `ajustes`) e `c3993055bd44`
   (ponta da `main`). Sem isto o `alembic upgrade head` recusa com "múltiplas
   heads".
2. **Recria `cronograma_reajuste_solicitacao`**, que `72a7a5145a5a` dropou.
3. **Repõe os dois valores no enum de notificação** que a mesma reversão
   tirou. `use_cases/notificacao/eventos.py` voltou a registrar
   `reajuste_solicitado` e `reajuste_respondido`; sem eles no enum, o INSERT
   estoura no primeiro pedido.
4. **Devolve `projeto_escopo.cronograma_oficializado_em`** se ela não estiver
   lá. A migration `e93cec587f4a` da `ajustes` a dropa ("fim da
   oficialização"), mas a `main` tem um `OficializarCronogramaUseCase` vivo
   que escreve nela. Os dois conceitos passam a conviver: a janela do escopo
   não consulta a coluna, e o carimbo continua funcionando.

Os passos 2 e 4 checam o banco antes de agir, porque este merge alcança bancos
em estados diferentes: o de quem estava na `ajustes` já não tem a coluna e o de
quem estava na `main` já não tem a tabela.

Revision ID: b1c4d7e90a22
Revises: a7c31d0b9e58, c3993055bd44
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b1c4d7e90a22"
down_revision: Union[str, Sequence[str], None] = ("a7c31d0b9e58", "c3993055bd44")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: O enum como o modelo o declara depois do merge — os dois últimos são os que
#: a reversão da main havia tirado.
TIPOS_NOTIFICACAO = [
    "alocado_em_projeto",
    "entrega_registrada",
    "banca_remarcada",
    "entrega_alterada",
    "escalacao_banca",
    "troca_banca",
    "avaliacao_pendente",
    "banca_aviso",
    "lote_desempenho_aberto",
    "pdi_prazo_proximo",
    "pdi_prazo_vencido",
    "kickoff_pendente",
    "tarefa_vencida",
    "banca_nao_marcada",
    "projeto_sem_reuniao",
    "banca_hoje",
    "reajuste_solicitado",
    "reajuste_respondido",
]


def _tem_tabela(nome: str) -> bool:
    return nome in sa.inspect(op.get_bind()).get_table_names()


def _tem_coluna(tabela: str, coluna: str) -> bool:
    inspetor = sa.inspect(op.get_bind())
    if tabela not in inspetor.get_table_names():
        return False
    return coluna in {c["name"] for c in inspetor.get_columns(tabela)}


def _redefinir_enum_notificacao(valores) -> None:
    """O enum de `notificacao.tipo` nos dois dialetos que o projeto usa."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        from src.utils.alembic_pg import redefinir_enum_postgres

        redefinir_enum_postgres(op, "notificacao", "tipo", "tipo_notificacao", list(valores))
    else:
        op.alter_column(
            "notificacao",
            "tipo",
            type_=sa.Enum(*valores, name="tipo_notificacao"),
            existing_nullable=False,
        )


def upgrade() -> None:
    # 2 · A tabela do pedido de dias, com `dias_solicitados` já dentro — ela
    # nasceu em `9a4f6184cba9` sem a coluna, que veio depois em
    # `e93cec587f4a`. Recriar em duas etapas seria fiel à história e inútil.
    if not _tem_tabela("cronograma_reajuste_solicitacao"):
        op.create_table(
            "cronograma_reajuste_solicitacao",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("projeto_escopo_id", sa.Integer(), nullable=False),
            sa.Column("solicitado_por", sa.Integer(), nullable=False),
            sa.Column("dias_solicitados", sa.Integer(), nullable=False),
            sa.Column("motivo", sa.String(length=500), nullable=False),
            sa.Column(
                "status",
                sa.Enum("pendente", "aprovado", "rejeitado", name="status_reajuste_cronograma"),
                server_default="pendente",
                nullable=False,
            ),
            sa.Column("respondido_por", sa.Integer(), nullable=True),
            sa.Column("resposta_justificativa", sa.String(length=500), nullable=True),
            sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("respondido_em", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["projeto_escopo_id"], ["projeto_escopo.id"]),
            sa.ForeignKeyConstraint(["respondido_por"], ["usuario.id"]),
            sa.ForeignKeyConstraint(["solicitado_por"], ["usuario.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_cronograma_reajuste_solicitacao_id"),
            "cronograma_reajuste_solicitacao",
            ["id"],
            unique=False,
        )

    # 3 · Os dois tipos de notificação do fluxo restaurado.
    _redefinir_enum_notificacao(TIPOS_NOTIFICACAO)

    # 4 · O carimbo de oficialização, que a `main` ainda escreve.
    if not _tem_coluna("projeto_escopo", "cronograma_oficializado_em"):
        op.add_column(
            "projeto_escopo", sa.Column("cronograma_oficializado_em", sa.DateTime(), nullable=True)
        )


def downgrade() -> None:
    """⚠ Volta ao estado da `main`: sem pedido de dias.

    As solicitações registradas somem junto com a tabela — não há para onde
    movê-las, o conceito deixa de existir. As notificações dos dois tipos são
    apagadas antes de estreitar o enum, senão o ALTER falha (ou trunca) nas
    linhas que ainda os usam.
    """
    if _tem_coluna("projeto_escopo", "cronograma_oficializado_em"):
        op.drop_column("projeto_escopo", "cronograma_oficializado_em")

    op.execute(
        "DELETE FROM notificacao WHERE tipo IN ('reajuste_solicitado', 'reajuste_respondido')"
    )
    _redefinir_enum_notificacao(
        [t for t in TIPOS_NOTIFICACAO if not t.startswith("reajuste_")]
    )

    if _tem_tabela("cronograma_reajuste_solicitacao"):
        op.drop_table("cronograma_reajuste_solicitacao")
