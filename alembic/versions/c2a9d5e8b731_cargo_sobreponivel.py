"""cargo_sobreponivel

Revision ID: c2a9d5e8b731
Revises: f8b3c6d0a417
Create Date: 2026-09-22 22:30:00.000000

⭐ 2026-09-22 — a pedido: generaliza `usuario.cargo_extra` (antes hardcoded
só pra "bdr" em cima de "consultor"). `posicao_permissao.sobreponivel`
decide, na hora de criar/editar o cargo, se ele pode ser cargo extra de
qualquer pessoa. Backfill: "bdr" é o único cargo hoje usado como extra —
vira `True` pra não quebrar quem já tem BDR marcado; os outros 5 padrão
ficam `False` (nunca foram extra, continuam não sendo).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c2a9d5e8b731'
down_revision: Union[str, Sequence[str], None] = 'f8b3c6d0a417'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("sobreponivel", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE posicao_permissao SET sobreponivel = true WHERE posicao = 'bdr'")


def downgrade() -> None:
    op.drop_column("posicao_permissao", "sobreponivel")
