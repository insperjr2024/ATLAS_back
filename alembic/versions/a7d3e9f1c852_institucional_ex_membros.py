"""institucional: ex-membros do site + caixa "acessar institucional"

Revision ID: a7d3e9f1c852
Revises: e5b9c3d7a241
Create Date: 2026-10-09

A pedido: a seção "Ex-membros" do site institucional deixa de ser uma lista
fixa no código do site e passa a ser editada pela aba Institucional do ATLAS.
Ver `models/ex_membro_model.py`. A caixa nasce marcada só pros três cargos
de diretoria.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7d3e9f1c852"
down_revision: Union[str, Sequence[str], None] = "e5b9c3d7a241"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIRETORIA = ("diretor_projetos", "diretor_pessoas", "diretor")


def upgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_acessar_institucional", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        sa.text(
            "UPDATE posicao_permissao SET pode_acessar_institucional = TRUE WHERE posicao IN :posicoes"
        ).bindparams(sa.bindparam("posicoes", expanding=True, value=list(DIRETORIA)))
    )

    op.create_table(
        "ex_membro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("cargo_pt", sa.String(length=150), nullable=False),
        sa.Column("cargo_en", sa.String(length=150), nullable=True),
        sa.Column("area_pt", sa.String(length=150), nullable=True),
        sa.Column("area_en", sa.String(length=150), nullable=True),
        sa.Column("empresa", sa.String(length=150), nullable=False),
        sa.Column("empresa_en", sa.String(length=150), nullable=True),
        sa.Column("depoimento_pt", sa.Text(), nullable=True),
        sa.Column("depoimento_en", sa.Text(), nullable=True),
        sa.Column("linkedin", sa.String(length=300), nullable=True),
        sa.Column("foto", sa.LargeBinary(), nullable=True),
        sa.Column("foto_versao", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("publicado", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_por", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ex_membro_id"), "ex_membro", ["id"])
    op.create_index(op.f("ix_ex_membro_ordem"), "ex_membro", ["ordem"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ex_membro_ordem"), table_name="ex_membro")
    op.drop_index(op.f("ix_ex_membro_id"), table_name="ex_membro")
    op.drop_table("ex_membro")
    op.drop_column("posicao_permissao", "pode_acessar_institucional")
