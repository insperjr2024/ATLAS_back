"""remove_pode_ver_nucleo

Revision ID: f81c58ed626c
Revises: 09c89168322d
Create Date: 2026-08-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = "f81c58ed626c"
down_revision = "09c89168322d"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("cargo", "pode_ver_nucleo")


def downgrade():
    op.add_column(
        "cargo",
        sa.Column("pode_ver_nucleo", mysql.TINYINT(display_width=1), autoincrement=False, nullable=False),
    )
