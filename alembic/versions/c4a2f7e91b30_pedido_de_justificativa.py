"""§7.4: o pedido de justificativa — a diretoria pergunta, o coordenador responde

Revision ID: c4a2f7e91b30
Revises: bb6fdb2cd834
Create Date: 2026-08-13
"""

import sqlalchemy as sa
from alembic import op

revision = "c4a2f7e91b30"
down_revision = "bb6fdb2cd834"
branch_labels = None
depends_on = None


#: Os valores que já existiam, mais o novo. MySQL exige a lista inteira num
#: ALTER; o Postgres só o valor novo (ver o bloco no fim).
TIPOS = [
    "alocado_em_projeto",
    "solicitacao_projeto",
    "entrega_registrada",
    "banca_remarcada",
    "entrega_alterada",
    "justificativa_pedida",
    #: ⚠ Estes dois não estão no enum do model (`notificacao_model.py`) e
    #: ESTÃO na coluna e em uso. Omiti-los aqui trunca as linhas gravadas com
    #: eles — foi o que aconteceu na primeira tentativa desta migration. A
    #: lista de um ALTER de ENUM tem de descrever o BANCO, não o model.
    "reajuste_solicitado",
    "reajuste_respondido",
    "escalacao_banca",
    "troca_banca",
    "avaliacao_pendente",
    "banca_aviso",
    "lote_desempenho_aberto",
    "pdi_prazo_proximo",
    "pdi_prazo_vencido",
    "kickoff_pendente",
    "tarefa_vencida",
    "descricao_coordenador_pendente",
    "banca_nao_marcada",
    "projeto_sem_reuniao",
    "banca_hoje",
]


def upgrade() -> None:
    op.create_table(
        "justificativa_pedido",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("projeto_id", sa.Integer(), nullable=False),
        sa.Column("projeto_escopo_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=30), nullable=True),
        sa.Column("solicitado_por", sa.Integer(), nullable=False),
        sa.Column(
            "solicitado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("respondido_em", sa.DateTime(), nullable=True),
        sa.Column("justificativa_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
        sa.ForeignKeyConstraint(["projeto_escopo_id"], ["projeto_escopo.id"]),
        sa.ForeignKeyConstraint(["solicitado_por"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["justificativa_id"], ["projeto_justificativa_atraso.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # ⚠ O índice no `id` parece redundante (a PK já é indexada), mas é a
    # convenção do repo — `entrega_alteracao`, `banca_sessao` e
    # `projeto_justificativa_atraso` fazem igual, porque os models declaram
    # `index=True` na PK. Sem ele, o próximo `--autogenerate` de qualquer
    # pessoa nasce sujo com este índice.
    op.create_index(op.f("ix_justificativa_pedido_id"), "justificativa_pedido", ["id"])
    op.create_index(
        "ix_justificativa_pedido_projeto_id", "justificativa_pedido", ["projeto_id"]
    )

    # ⚠ **O enum de notificação diverge entre os dois bancos.**
    #
    # No MySQL o ENUM é propriedade da COLUNA: para acrescentar um valor,
    # reescreve-se a lista inteira. No Postgres é um TYPE compartilhado, e
    # `ADD VALUE` não roda dentro de transação — daí o `autocommit_block`.
    # Foi exatamente essa diferença que derrubou o deploy do
    # `descricao_coordenador_pendente`.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS 'justificativa_pedida'"
            )
    else:
        op.alter_column(
            "notificacao",
            "tipo",
            existing_type=sa.Enum(*[t for t in TIPOS if t != "justificativa_pedida"],
                                  name="tipo_notificacao"),
            type_=sa.Enum(*TIPOS, name="tipo_notificacao"),
            existing_nullable=False,
        )


def downgrade() -> None:
    """⚠ Só o `drop_table`, sem `drop_index` antes.

    No MySQL os índices de `projeto_id`, `projeto_escopo_id`, `solicitado_por`
    e `justificativa_id` sustentam as chaves estrangeiras: tentar apagá-los
    primeiro falha com "needed in a foreign key constraint" — foi o que
    aconteceu na primeira versão desta migration. Derrubar a tabela leva
    índices e FKs junto. Mesma nota está em `a7c31d0b9e58_entrega_alteracao`.
    """
    op.drop_table("justificativa_pedido")
    # ⚠ O valor do enum NÃO é removido: no Postgres não há `DROP VALUE`, e no
    # MySQL encolher a lista quebraria as linhas já gravadas com ele.
