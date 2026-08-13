"""banca_sessao — cada tentativa de uma banca

⭐ Nasce com BACKFILL: toda banca existente ganha a sessão nº 1, espelhando o
estado atual (`data_hora`, `realizado_em`, `resultado`). Sem isso, o histórico
de tentativas e a UI de "2ª banca" viriam vazios para tudo que já existe, e a
sessão corrente seria `None` numa banca perfeitamente normal.

A sessão nasce ENCERRADA quando a banca já tem veredito — uma banca aprovada
não tem sessão em aberto. Nos demais casos fica corrente (`encerrada_em` nulo).

Revision ID: b7e4c91a25f8
Revises: a3f1b8c27d40
Create Date: 2026-08-12 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e4c91a25f8"
down_revision: Union[str, Sequence[str], None] = "a3f1b8c27d40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "banca_sessao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("banca_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("data_hora", sa.DateTime(), nullable=True),
        sa.Column("realizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "resultado",
            sa.Enum("aprovada", "nao_aprovada", name="resultado_banca_sessao"),
            nullable=True,
        ),
        sa.Column("encerrada_em", sa.DateTime(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["banca_id"], ["banca.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("banca_id", "numero", name="uq_banca_sessao_numero"),
    )
    op.create_index(op.f("ix_banca_sessao_id"), "banca_sessao", ["id"])
    op.create_index(op.f("ix_banca_sessao_banca_id"), "banca_sessao", ["banca_id"])

    # ⚠ **`banca.resultado` e `banca_sessao.resultado` são enums DIFERENTES** —
    # `resultado_banca` e `resultado_banca_sessao`, com os mesmos valores mas
    # nomes distintos.
    #
    # Em MySQL isso não importa: o enum é propriedade da coluna e a cópia é de
    # texto para texto. Em Postgres o enum é um TIPO, e copiar de um tipo para
    # outro sem cast falha com "column resultado is of type
    # resultado_banca_sessao but expression is of type resultado_banca" —
    # derrubando o `upgrade` inteiro no meio.
    #
    # A ponte é o texto, e ela só existe no dialeto do Postgres. Mesmo padrão
    # condicional que `a71c4e93b8d2` usa para o `ALTER TYPE`.
    resultado = (
        "resultado::text::resultado_banca_sessao"
        if op.get_bind().dialect.name == "postgresql"
        else "resultado"
    )

    # ⭐ O backfill. `encerrada_em` sai preenchido só onde já há veredito — a
    # sessão de uma banca com resultado não está mais em aberto.
    op.execute(
        f"""
        INSERT INTO banca_sessao
            (banca_id, numero, data_hora, realizado_em, resultado, encerrada_em, criado_em)
        SELECT
            id, 1, data_hora, realizado_em, {resultado},
            CASE WHEN resultado IS NOT NULL THEN realizado_em ELSE NULL END,
            now()
        FROM banca
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_banca_sessao_banca_id"), table_name="banca_sessao")
    op.drop_index(op.f("ix_banca_sessao_id"), table_name="banca_sessao")
    op.drop_table("banca_sessao")
