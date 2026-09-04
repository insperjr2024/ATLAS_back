"""aprovacao de banca por diretoria ou gerente da frente

O resultado da banca deixa de sair da maioria dos votos dos avaliadores
(`avaliacao.voto_aprovacao`) e passa a ser a decisão de diretoria de projetos
OU gerente de qualquer frente da banca (ver `utils/apuracao_banca.py` e
`use_cases/banca/aprovar_banca.py`) — qualquer um decide sozinho, sem esperar
o outro.

`voto_aprovacao` sai sem migração de dado: a decisão foi não preservar
histórico de voto (o veredito já gravado em `banca.resultado` continua
intacto, só muda quem decide daqui pra frente).

Revision ID: 8b9d69103957
Revises: 4f878bd409aa
Create Date: 2026-09-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b9d69103957"
down_revision: Union[str, Sequence[str], None] = "4f878bd409aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("avaliacao", "voto_aprovacao")

    op.create_table(
        "banca_aprovacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("banca_id", sa.Integer(), nullable=False),
        sa.Column("papel", sa.Enum("diretoria", "gerente", name="papel_aprovacao_banca"), nullable=False),
        sa.Column("frente_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("aprovado", sa.Boolean(), nullable=False),
        sa.Column("nota", sa.String(length=500), nullable=True),
        sa.Column("sessao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["banca_id"], ["banca.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["frente_id"], ["frente.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_banca_aprovacao_banca_id"), "banca_aprovacao", ["banca_id"], unique=False)
    op.create_index(op.f("ix_banca_aprovacao_id"), "banca_aprovacao", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_banca_aprovacao_id"), table_name="banca_aprovacao")
    op.drop_index(op.f("ix_banca_aprovacao_banca_id"), table_name="banca_aprovacao")
    op.drop_table("banca_aprovacao")
    sa.Enum(name="papel_aprovacao_banca").drop(op.get_bind(), checkfirst=True)

    op.add_column("avaliacao", sa.Column("voto_aprovacao", sa.Boolean(), nullable=True))
