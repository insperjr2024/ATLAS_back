"""endereco_estruturado_presidente

Revision ID: db182fa99145
Revises: 672d807ec8d9
Create Date: 2026-09-21 17:05:36.659582

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db182fa99145'
down_revision: Union[str, Sequence[str], None] = '672d807ec8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "identidade_institucional",
        sa.Column("presidente_endereco_rua", sa.String(length=255), nullable=False,
                   server_default="Rua Casa do Ator"),
    )
    op.add_column(
        "identidade_institucional",
        sa.Column("presidente_endereco_numero", sa.String(length=20), nullable=False, server_default="829"),
    )
    op.add_column(
        "identidade_institucional",
        sa.Column("presidente_endereco_complemento", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "identidade_institucional",
        sa.Column("presidente_endereco_bairro", sa.String(length=100), nullable=False,
                   server_default="Vila Olímpia"),
    )
    op.add_column(
        "identidade_institucional",
        sa.Column("presidente_endereco_cidade", sa.String(length=100), nullable=False,
                   server_default="São Paulo"),
    )
    op.add_column(
        "identidade_institucional",
        sa.Column("presidente_endereco_estado", sa.String(length=2), nullable=False, server_default="SP"),
    )
    op.add_column(
        "identidade_institucional",
        sa.Column("presidente_endereco_cep", sa.String(length=20), nullable=False, server_default="04546-003"),
    )
    op.drop_column("identidade_institucional", "presidente_endereco")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "identidade_institucional",
        sa.Column("presidente_endereco", sa.String(length=500), nullable=False,
                   server_default="Rua Casa do Ator, nº 829, Vila Olímpia, CEP: 4546003, São Paulo/SP"),
    )
    op.drop_column("identidade_institucional", "presidente_endereco_cep")
    op.drop_column("identidade_institucional", "presidente_endereco_estado")
    op.drop_column("identidade_institucional", "presidente_endereco_cidade")
    op.drop_column("identidade_institucional", "presidente_endereco_bairro")
    op.drop_column("identidade_institucional", "presidente_endereco_complemento")
    op.drop_column("identidade_institucional", "presidente_endereco_numero")
    op.drop_column("identidade_institucional", "presidente_endereco_rua")
