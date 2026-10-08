"""arquivo de contratos: pastas, itens e a caixa de permissão

Revision ID: c9f1b3e7a526
Revises: b4e8a2c6d719
Create Date: 2026-10-07

Ver `models/arquivo_contratos_model.py`. A caixa
`pode_acessar_arquivo_contratos` nasce desmarcada pra todo mundo: a
diretoria escolhe quem entra.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9f1b3e7a526"
down_revision: Union[str, Sequence[str], None] = "b4e8a2c6d719"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ORIGEM = sa.Enum("atlas", "importado", name="arquivo_contratos_origem")
# Na coluna, o ENUM do dialeto Postgres com `create_type=False`: o tipo é
# criado uma vez, explicitamente, no `upgrade`; o `sa.Enum` genérico ignora
# esse argumento e o `create_table` tentava criar o tipo de novo.
ORIGEM_COLUNA = postgresql.ENUM("atlas", "importado", name="arquivo_contratos_origem", create_type=False)


def upgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_acessar_arquivo_contratos", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "arquivo_contratos_pasta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("pai_id", sa.Integer(), sa.ForeignKey("arquivo_contratos_pasta.id", ondelete="CASCADE"), nullable=True),
        sa.Column("semestre_id", sa.Integer(), sa.ForeignKey("semestre.id", ondelete="SET NULL"), nullable=True),
        sa.Column("projeto_id", sa.Integer(), sa.ForeignKey("projeto.id", ondelete="SET NULL"), nullable=True),
        sa.Column("criado_por", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("semestre_id", name="uq_arquivo_contratos_pasta_semestre"),
        sa.UniqueConstraint("pai_id", "projeto_id", name="uq_arquivo_contratos_pasta_projeto"),
    )
    op.create_index(op.f("ix_arquivo_contratos_pasta_id"), "arquivo_contratos_pasta", ["id"])
    op.create_index("ix_arquivo_contratos_pasta_pai_id", "arquivo_contratos_pasta", ["pai_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DO $$ BEGIN CREATE TYPE arquivo_contratos_origem AS ENUM ('atlas', 'importado'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )
    else:
        ORIGEM.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "arquivo_contratos_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pasta_id", sa.Integer(), sa.ForeignKey("arquivo_contratos_pasta.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=120), nullable=False),
        sa.Column("tamanho", sa.Integer(), nullable=False),
        sa.Column("conteudo", sa.LargeBinary(), nullable=False),
        sa.Column("origem", ORIGEM_COLUNA, nullable=False, server_default="importado"),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documento_contratual.id", ondelete="SET NULL"), nullable=True),
        sa.Column("criado_por", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_arquivo_contratos_item_id"), "arquivo_contratos_item", ["id"])
    op.create_index("ix_arquivo_contratos_item_pasta_id", "arquivo_contratos_item", ["pasta_id"])
    op.create_index("ix_arquivo_contratos_item_documento_id", "arquivo_contratos_item", ["documento_id"])


def downgrade() -> None:
    op.drop_table("arquivo_contratos_item")
    op.drop_table("arquivo_contratos_pasta")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS arquivo_contratos_origem")
    op.drop_column("posicao_permissao", "pode_acessar_arquivo_contratos")
