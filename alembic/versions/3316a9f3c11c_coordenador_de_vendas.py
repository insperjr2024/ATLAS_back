"""coordenador de vendas

Revision ID: 3316a9f3c11c
Revises: e7b3c419d0a5
Create Date: 2026-09-01

Marca um coordenador como sendo de vendas (comercial). Ele mantem a posicao
`coordenador` e o mesmo acesso, mas sai da contagem de capacidade de
coordenadores no Monitoramento, onde aparecia como "0 projetos, disponivel" e
inflava a folga do nucleo.

Nasce `false` para todo mundo. A diretoria marca quem for pelo cadastro do
membro.
"""

import sqlalchemy as sa
from alembic import op

revision = "3316a9f3c11c"
down_revision = "e7b3c419d0a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column(
            "coordenador_vendas",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("usuario", "coordenador_vendas")
