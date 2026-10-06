"""periódica · escopo nasce igual à finalização · escopo

Revision ID: a9d4e7c2b185
Revises: e3c7a1f5b928
Create Date: 2026-10-05

A pedido: em vez de a diretoria montar o formulário da periódica do zero,
ele começa como cópia do da finalização (textos, seções e critérios). Os
dois continuam independentes depois: editar um não mexe no outro.

Só copia se a periódica ainda não tem seção nenhuma, pra não passar por
cima de algo que alguém já tenha montado na tela.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9d4e7c2b185"
down_revision: Union[str, Sequence[str], None] = "e3c7a1f5b928"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _formulario(conn, tipo: str):
    return conn.execute(
        sa.text("SELECT id FROM desempenho_formulario WHERE tipo = :tipo AND papel = 'escopo'"),
        {"tipo": tipo},
    ).first()


def upgrade() -> None:
    conn = op.get_bind()
    origem = _formulario(conn, "finalizacao")
    destino = _formulario(conn, "periodico")
    if not origem or not destino:
        return
    ja_tem = conn.execute(
        sa.text("SELECT 1 FROM desempenho_formulario_secao WHERE formulario_id = :id LIMIT 1"),
        {"id": destino.id},
    ).first()
    if ja_tem:
        return

    conn.execute(
        sa.text(
            """
            UPDATE desempenho_formulario d
               SET nota_geral_titulo = o.nota_geral_titulo,
                   nota_geral_descricao = o.nota_geral_descricao,
                   comentarios_titulo = o.comentarios_titulo,
                   comentarios_descricao = o.comentarios_descricao,
                   comentarios_aviso = o.comentarios_aviso
              FROM desempenho_formulario o
             WHERE d.id = :destino AND o.id = :origem
            """
        ),
        {"destino": destino.id, "origem": origem.id},
    )

    secoes = conn.execute(
        sa.text(
            "SELECT id, titulo, descricao, ordem FROM desempenho_formulario_secao "
            "WHERE formulario_id = :id ORDER BY ordem, id"
        ),
        {"id": origem.id},
    ).fetchall()
    for secao in secoes:
        nova = conn.execute(
            sa.text(
                "INSERT INTO desempenho_formulario_secao (formulario_id, titulo, descricao, ordem) "
                "VALUES (:formulario_id, :titulo, :descricao, :ordem) RETURNING id"
            ),
            {
                "formulario_id": destino.id,
                "titulo": secao.titulo,
                "descricao": secao.descricao,
                "ordem": secao.ordem,
            },
        ).scalar_one()
        conn.execute(
            sa.text(
                "INSERT INTO desempenho_criterio (secao_id, label, descricao, tipo_resposta, limite_caracteres, ordem) "
                "SELECT :nova, label, descricao, tipo_resposta, limite_caracteres, ordem "
                "FROM desempenho_criterio WHERE secao_id = :antiga"
            ),
            {"nova": nova, "antiga": secao.id},
        )


def downgrade() -> None:
    """Apaga as seções da periódica (os critérios vão em cascata). Não dá pra
    saber se foram as copiadas ou editadas depois, então é tudo ou nada."""
    conn = op.get_bind()
    destino = _formulario(conn, "periodico")
    if destino:
        conn.execute(
            sa.text("DELETE FROM desempenho_formulario_secao WHERE formulario_id = :id"),
            {"id": destino.id},
        )
