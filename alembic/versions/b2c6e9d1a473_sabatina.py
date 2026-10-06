"""sabatina: eleições, candidatos, votos e peso por posição

Revision ID: b2c6e9d1a473
Revises: d1b8f4a6e372
Create Date: 2026-10-05

Ver `models/sabatina_model.py`. O peso é semeado pra cada posição que
existe hoje no catálogo (`posicao_permissao`) com a regra padrão: diretoria
3, gerente e coordenador 2, o resto 1. Posição criada depois usa o mesmo
padrão até alguém editar na tela.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c6e9d1a473"
down_revision: Union[str, Sequence[str], None] = "d1b8f4a6e372"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _peso_padrao(posicao: str) -> int:
    p = posicao.lower()
    if p.startswith("diretor") or p in ("presidente", "presidencia"):
        return 3
    if p in ("gerente", "coordenador"):
        return 2
    return 1


def upgrade() -> None:
    peso = op.create_table(
        "sabatina_peso",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "posicao",
            sa.String(length=50),
            sa.ForeignKey("posicao_permissao.posicao", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("peso", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("posicao"),
    )
    op.create_index(op.f("ix_sabatina_peso_id"), "sabatina_peso", ["id"], unique=False)

    op.create_table(
        "sabatina_eleicao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("percentual_aprovacao", sa.Integer(), server_default="50", nullable=False),
        sa.Column(
            "status",
            sa.Enum("rascunho", "aberta", "fechada", name="status_sabatina_eleicao"),
            server_default="rascunho",
            nullable=False,
        ),
        sa.Column("eleitores_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("criado_por", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("aberta_em", sa.DateTime(), nullable=True),
        sa.Column("fechada_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sabatina_eleicao_id"), "sabatina_eleicao", ["id"], unique=False)

    op.create_table(
        "sabatina_candidato",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "eleicao_id", sa.Integer(), sa.ForeignKey("sabatina_eleicao.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("ordem", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("eleicao_id", "usuario_id", name="uq_sabatina_candidato"),
    )
    op.create_index(op.f("ix_sabatina_candidato_id"), "sabatina_candidato", ["id"], unique=False)
    op.create_index("ix_sabatina_candidato_eleicao_id", "sabatina_candidato", ["eleicao_id"])
    op.create_index("ix_sabatina_candidato_usuario_id", "sabatina_candidato", ["usuario_id"])

    op.create_table(
        "sabatina_voto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "eleicao_id", sa.Integer(), sa.ForeignKey("sabatina_eleicao.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("eleitor_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column(
            "candidato_id",
            sa.Integer(),
            sa.ForeignKey("sabatina_candidato.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("posicao", sa.String(length=50), nullable=False),
        sa.Column("peso", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("eleicao_id", "eleitor_id", name="uq_sabatina_voto_eleitor"),
    )
    op.create_index(op.f("ix_sabatina_voto_id"), "sabatina_voto", ["id"], unique=False)
    op.create_index("ix_sabatina_voto_eleicao_id", "sabatina_voto", ["eleicao_id"])
    op.create_index("ix_sabatina_voto_eleitor_id", "sabatina_voto", ["eleitor_id"])
    op.create_index("ix_sabatina_voto_candidato_id", "sabatina_voto", ["candidato_id"])

    posicoes = [r[0] for r in op.get_bind().execute(sa.text("SELECT posicao FROM posicao_permissao")).fetchall()]
    if posicoes:
        op.bulk_insert(peso, [{"posicao": p, "peso": _peso_padrao(p)} for p in posicoes])


def downgrade() -> None:
    op.drop_table("sabatina_voto")
    op.drop_table("sabatina_candidato")
    op.drop_table("sabatina_eleicao")
    op.drop_table("sabatina_peso")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS status_sabatina_eleicao")
