"""documento_contratual_criado_por

Revision ID: c1b1fbcf9f4d
Revises: 9d3d7bbda04a
Create Date: 2026-09-23 00:00:00.000000

⭐ 2026-09-23 — a pedido: quem criou o documento (abriu o "Novo Contrato")
não era registrado em lugar nenhum — nem `confirmado_por` (quem preencheu)
nem `aprovado_internamente_por` (o jurídico) respondem "quem criou".
Nullable: documentos de antes desta coluna existir ficam sem essa
informação, sem como reconstruir depois do fato.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c1b1fbcf9f4d'
down_revision: Union[str, Sequence[str], None] = '9d3d7bbda04a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'documento_contratual',
        sa.Column('criado_por', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_documento_contratual_criado_por',
        'documento_contratual',
        'usuario',
        ['criado_por'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_documento_contratual_criado_por', 'documento_contratual', type_='foreignkey')
    op.drop_column('documento_contratual', 'criado_por')
