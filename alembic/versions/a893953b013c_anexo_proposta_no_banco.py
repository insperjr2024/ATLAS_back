"""anexo da proposta no banco

Revision ID: a893953b013c
Revises: 3316a9f3c11c
Create Date: 2026-09-01

O PDF da proposta passa a ser gravado no proprio banco (`anexo_proposta_conteudo`,
BYTEA) em vez de um arquivo em disco apontado por `anexo_proposta_path`.

O disco do servidor de deploy e efemero: sumia a cada redeploy, e os projetos
ficavam com um caminho no banco apontando para um arquivo que nao existia mais.
Mesma escolha do envio de PDI, que ja guarda o conteudo no banco pelo mesmo
motivo.

Nao ha o que migrar: os arquivos antigos ja se perderam nos redeploys. Os
projetos que tinham anexo ficam com `anexo_proposta_conteudo` NULL e o nome
preservado; o download avisa que o arquivo se perdeu e pede reenvio.
"""

import sqlalchemy as sa
from alembic import op

revision = "a893953b013c"
down_revision = "3316a9f3c11c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projeto",
        sa.Column("anexo_proposta_conteudo", sa.LargeBinary(), nullable=True),
    )
    op.drop_column("projeto", "anexo_proposta_path")


def downgrade() -> None:
    op.add_column(
        "projeto",
        sa.Column("anexo_proposta_path", sa.String(length=255), nullable=True),
    )
    op.drop_column("projeto", "anexo_proposta_conteudo")
