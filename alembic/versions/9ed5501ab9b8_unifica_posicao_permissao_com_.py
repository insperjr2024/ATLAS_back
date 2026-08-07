"""unifica posicao_permissao com solicitacao de projeto

Revision ID: 9ed5501ab9b8
Revises: 03ea41a273d0, d66e88dfc475, ef365a1cc656
Create Date: 2026-08-07 05:19:56.379344

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ed5501ab9b8'
down_revision: Union[str, Sequence[str], None] = ('03ea41a273d0', 'd66e88dfc475', 'ef365a1cc656')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
