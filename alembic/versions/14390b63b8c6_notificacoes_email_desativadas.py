"""notificacoes_email_desativadas

Revision ID: 14390b63b8c6
Revises: a1c2d3e4f5b6
Create Date: 2026-08-17 00:49:52.539281

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14390b63b8c6'
down_revision: Union[str, Sequence[str], None] = 'a1c2d3e4f5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Só a coluna nova — o autogenerate também detectou uma pilha de drift
    # não relacionado (índices, tipo de `solicitacao_projeto.status`) que já
    # existia entre o banco e os models antes desta migration; não é desta
    # mudança, e entrar aqui misturado seria arriscar uma alteração de
    # verdade sem revisão nenhuma.
    op.add_column('usuario', sa.Column('notificacoes_email_desativadas', sa.JSON(), server_default='[]', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('usuario', 'notificacoes_email_desativadas')
