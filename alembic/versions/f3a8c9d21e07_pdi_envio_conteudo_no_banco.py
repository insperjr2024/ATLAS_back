"""pdi_envio_conteudo_no_banco

Revision ID: f3a8c9d21e07
Revises: 082aef445ead
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3a8c9d21e07'
down_revision: Union[str, Sequence[str], None] = '082aef445ead'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # O conteúdo passa a morar no banco (`arquivo_conteudo`), não mais em
    # disco (`arquivo_path`) — o disco do Render é efêmero e some a cada
    # redeploy/restart, então todo envio existente já perdeu o arquivo de
    # verdade. Sem como fazer backfill: limpa as linhas órfãs pra elas
    # voltarem a aparecer como "não enviado" (a pessoa reenvia limpo).
    op.execute("DELETE FROM desempenho_pdi_envio")

    op.add_column('desempenho_pdi_envio', sa.Column('arquivo_conteudo', sa.LargeBinary(), nullable=False))
    op.drop_column('desempenho_pdi_envio', 'arquivo_path')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('desempenho_pdi_envio', sa.Column('arquivo_path', sa.String(length=255), nullable=False))
    op.drop_column('desempenho_pdi_envio', 'arquivo_conteudo')
