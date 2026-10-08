"""notificações da rodada do Health Track

Revision ID: e5b9c3d7a241
Revises: d2f6a8c4e117
Create Date: 2026-10-08

Dois tipos novos em `tipo_notificacao`: rodada aberta (pra quem tem a caixa
do Health Track) e rodada parada com pendentes (pra diretoria de projetos).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e5b9c3d7a241"
down_revision: Union[str, Sequence[str], None] = "d2f6a8c4e117"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIPOS = ("rodada_health_track_aberta", "rodada_health_track_pendente")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        for tipo in TIPOS:
            op.execute(f"ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS '{tipo}'")


def downgrade() -> None:
    pass
