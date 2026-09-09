"""formulário "Avaliação do Escopo" — auto-avaliação na finalização

Revision ID: b5f1e0d9c473
Revises: a2c8f61de930
Create Date: 2026-09-09

⭐ A pedido, urgente. Um 5º formulário de desempenho: `(finalizacao, escopo)`.
Não é avaliação par a par — cada participante do projeto responde UMA vez
sobre o escopo finalizado, junto com a rodada de finalização. Reusa a
máquina de fila/submissão como auto-avaliação (par onde avaliador =
avaliado), pra não reescrever a arquitetura.

`escopo` entra como valor do enum de PAPEL (não de tipo) porque o front
resolve o formulário por `(lote_tipo, form_type)` — e o lote continua sendo
o de `finalizacao`.

⚠ `ALTER TYPE ... ADD VALUE` fora do bloco transacional (autocommit_block),
igual `e4b1d7c9a052` / `a2c8f61de930`. O INSERT do seed vem depois, já
enxergando o valor novo (Postgres 12+).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b5f1e0d9c473"
down_revision: Union[str, Sequence[str], None] = "a2c8f61de930"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"
    if is_pg:
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE desempenho_formulario_papel ADD VALUE IF NOT EXISTS 'escopo'"
            )

    # Seed do formulário em branco — os NOT NULL precisam de algo; a
    # diretoria edita tudo pela tela de Formulários depois. `ON CONFLICT DO
    # NOTHING` pela UNIQUE(tipo, papel), pra migration ser idempotente.
    conflito = "ON CONFLICT (tipo, papel) DO NOTHING" if is_pg else ""
    op.execute(
        f"""
        INSERT INTO desempenho_formulario
            (tipo, papel, nota_geral_titulo, nota_geral_descricao,
             comentarios_titulo, comentarios_descricao, comentarios_aviso)
        VALUES
            ('finalizacao', 'escopo',
             'Avaliação geral do escopo',
             'Dê uma nota geral para o escopo finalizado.',
             'Comentários',
             'Escreva livremente sobre o escopo finalizado.',
             'Este texto é lido pela diretoria.')
        {conflito}
        """
    )


def downgrade() -> None:
    """Remove só a linha do seed. O valor do enum fica — Postgres não tira
    valor de enum sem recriar o tipo, e um valor a mais é inofensivo."""
    op.execute(
        "DELETE FROM desempenho_formulario WHERE tipo = 'finalizacao' AND papel = 'escopo'"
    )
