"""bdr

Revision ID: 7f472ea3f8eb
Revises: a893953b013c
Create Date: 2026-09-02

Marca um consultor como BDR: alguem que tambem prospecta e fecha projeto. Nao
muda posicao nem acesso, so faz a pessoa aparecer na lista "quem vendeu o
projeto" do cadastro, ao lado dos coordenadores de vendas.

Nasce `false` para todo mundo. A diretoria marca quem for pelo cadastro do
membro.
"""

import sqlalchemy as sa
from alembic import op

revision = "7f472ea3f8eb"
down_revision = "a893953b013c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column("bdr", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("usuario", "bdr")
