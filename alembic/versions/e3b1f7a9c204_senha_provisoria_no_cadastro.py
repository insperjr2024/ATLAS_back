"""senha_provisoria_no_cadastro

O membro cadastrado pela diretoria recebe uma senha provisória por e-mail e é
obrigado a definir a dele no primeiro acesso. Esta coluna é o "ainda não
definiu": enquanto ela for verdadeira, o login funciona mas a plataforma fica
travada na tela de definir senha.

`server_default="0"`: as linhas que já existem são de quem já tem senha
própria — ninguém é empurrado para a tela de definição por causa desta
migration.

Revision ID: e3b1f7a9c204
Revises: a1c7e4b93d20
Create Date: 2026-08-06 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3b1f7a9c204'
down_revision: Union[str, Sequence[str], None] = 'a1c7e4b93d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'usuario',
        sa.Column(
            'senha_provisoria',
            sa.Boolean(),
            nullable=False,
            # `false`, não `sa.text('0')`: um 0 cru sem aspas no DEFAULT não
            # converte pra boolean sozinho no Postgres (o MySQL aceita).
            server_default=sa.text('false'),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('usuario', 'senha_provisoria')
