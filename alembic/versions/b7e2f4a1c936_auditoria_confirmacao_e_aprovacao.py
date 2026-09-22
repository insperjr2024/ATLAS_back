"""auditoria_confirmacao_e_aprovacao

Revision ID: b7e2f4a1c936
Revises: f2a6b9d3c847
Create Date: 2026-09-22 14:00:00.000000

⭐ 2026-09-22 — a pedido: quem confirmou o preenchimento (`confirmado_por`)
e quem aprovou internamente, quando (`aprovado_internamente_por`/`_em`) —
um registro de auditoria visível na tela ("Aprovado por Fulana às 14h32"),
não só uma notificação que some do sino depois de lida.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7e2f4a1c936'
down_revision: Union[str, Sequence[str], None] = 'f2a6b9d3c847'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documento_contratual", sa.Column("confirmado_por", sa.Integer(), nullable=True))
    op.add_column(
        "documento_contratual", sa.Column("aprovado_internamente_por", sa.Integer(), nullable=True)
    )
    op.add_column(
        "documento_contratual", sa.Column("aprovado_internamente_em", sa.DateTime(), nullable=True)
    )
    op.create_foreign_key(
        "fk_documento_contratual_confirmado_por", "documento_contratual", "usuario", ["confirmado_por"], ["id"]
    )
    op.create_foreign_key(
        "fk_documento_contratual_aprovado_internamente_por",
        "documento_contratual",
        "usuario",
        ["aprovado_internamente_por"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_documento_contratual_aprovado_internamente_por", "documento_contratual", type_="foreignkey"
    )
    op.drop_constraint("fk_documento_contratual_confirmado_por", "documento_contratual", type_="foreignkey")
    op.drop_column("documento_contratual", "aprovado_internamente_em")
    op.drop_column("documento_contratual", "aprovado_internamente_por")
    op.drop_column("documento_contratual", "confirmado_por")
