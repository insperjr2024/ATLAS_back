"""documento contratual: conteudo no banco, nao caminho em disco

Revision ID: 672d807ec8d9
Revises: 90b7ee6d5e04
Create Date: 2026-09-18

Mesma correcao de `a893953b013c` (anexo da proposta): o disco do servidor de
deploy e efemero, sumia a cada redeploy, e o registro no banco ficava
apontando para um arquivo que nao existia mais. `docx_path`/`pdf_path` de
`documento_contratual_versao` tinham exatamente o mesmo problema, herdado
sem adaptar do sistema antigo Contratos (que rodava com disco persistente).
Documento juridico assinado e mais sensivel que uma proposta de venda.

Nao ha o que migrar: esta tabela so existe em `contratos-implementacao`,
nunca foi para producao.
"""

import sqlalchemy as sa
from alembic import op

revision = "672d807ec8d9"
down_revision = "90b7ee6d5e04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documento_contratual_versao",
        sa.Column("docx_conteudo", sa.LargeBinary(), nullable=False),
    )
    op.add_column(
        "documento_contratual_versao",
        sa.Column("pdf_conteudo", sa.LargeBinary(), nullable=False),
    )
    op.drop_column("documento_contratual_versao", "docx_path")
    op.drop_column("documento_contratual_versao", "pdf_path")


def downgrade() -> None:
    op.add_column(
        "documento_contratual_versao",
        sa.Column("docx_path", sa.String(length=500), nullable=False),
    )
    op.add_column(
        "documento_contratual_versao",
        sa.Column("pdf_path", sa.String(length=500), nullable=False),
    )
    op.drop_column("documento_contratual_versao", "docx_conteudo")
    op.drop_column("documento_contratual_versao", "pdf_conteudo")
