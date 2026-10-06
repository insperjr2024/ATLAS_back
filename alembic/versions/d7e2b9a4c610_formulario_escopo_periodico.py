"""formulário "Avaliação do Escopo" da periódica

Revision ID: d7e2b9a4c610
Revises: f1a9c47db235
Create Date: 2026-10-05

A pedido: a periódica também pode incluir a Avaliação do Escopo, só que
sobre o escopo EM ANDAMENTO (ver `utils/desempenho_escopo.py`). Como o front
resolve o formulário por `(lote_tipo, form_type)`, a periódica precisa da
sua própria linha `(periodico, escopo)`, e as perguntas de "como está indo"
não são as de "como foi", então um formulário separado é o certo mesmo.

O valor `escopo` do enum de papel já existe desde `b5f1e0d9c473`; aqui é só
o seed em branco, que a diretoria edita pela tela de Formulários.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d7e2b9a4c610"
down_revision: Union[str, Sequence[str], None] = "f1a9c47db235"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    is_pg = op.get_bind().dialect.name == "postgresql"
    conflito = "ON CONFLICT (tipo, papel) DO NOTHING" if is_pg else ""
    op.execute(
        f"""
        INSERT INTO desempenho_formulario
            (tipo, papel, nota_geral_titulo, nota_geral_descricao,
             comentarios_titulo, comentarios_descricao, comentarios_aviso)
        VALUES
            ('periodico', 'escopo',
             'Avaliação geral do escopo',
             'Dê uma nota geral para o andamento do escopo até aqui.',
             'Comentários',
             'Escreva livremente sobre o andamento do escopo.',
             'Este texto é lido pela diretoria.')
        {conflito}
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM desempenho_formulario WHERE tipo = 'periodico' AND papel = 'escopo'"
    )
