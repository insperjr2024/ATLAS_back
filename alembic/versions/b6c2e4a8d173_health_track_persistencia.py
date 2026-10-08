"""health track: limites de persistência

Revision ID: b6c2e4a8d173
Revises: a4d8e2c6f931
Create Date: 2026-10-08

Health Track §7: "cronograma amarelo há 3 avaliações" vira alerta a partir
de N avaliações seguidas na mesma cor. Os dois N (amarelo e vermelho) são
da diretoria, em Configurações, e moram na linha única de `configuracao`.
Padrão 2, como a spec sugere.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b6c2e4a8d173"
down_revision: Union[str, Sequence[str], None] = "a4d8e2c6f931"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "configuracao",
        sa.Column("health_track_persistencia_amarelo", sa.Integer(), server_default="2", nullable=False),
    )
    op.add_column(
        "configuracao",
        sa.Column("health_track_persistencia_vermelho", sa.Integer(), server_default="2", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("configuracao", "health_track_persistencia_vermelho")
    op.drop_column("configuracao", "health_track_persistencia_amarelo")
