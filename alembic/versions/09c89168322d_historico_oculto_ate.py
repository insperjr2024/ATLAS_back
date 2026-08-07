"""historico_oculto_ate

Revision ID: 09c89168322d
Revises: 1556cc590a06
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "09c89168322d"
down_revision = "1556cc590a06"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projeto", sa.Column("historico_oculto_ate", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("projeto", "historico_oculto_ate")
