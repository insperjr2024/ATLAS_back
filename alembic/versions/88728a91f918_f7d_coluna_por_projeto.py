"""f7d_coluna_por_projeto

As colunas do kanban deixam de ser uma configuração global e passam a
pertencer ao PROJETO: cada um tem o seu fluxo, e mexer no board de um não
mexe no dos outros.

⚠ Escrita à mão, não autogerada. O `--autogenerate` proporia apenas
"adiciona `projeto_id` NOT NULL", que falha na primeira linha existente e
não teria como decidir de qual projeto cada coluna global é — a resposta é
que ela vira UMA CÓPIA por projeto. A conversão é:

    1. adiciona `projeto_id` NULLABLE
    2. para cada projeto, CLONA as colunas globais existentes
    3. repõe cada tarefa na cópia do próprio projeto
    4. apaga as linhas globais, agora órfãs
    5. NOT NULL + a unicidade de `chave` passa a ser por projeto

Projeto que ainda não tem tarefa nenhuma também ganha as colunas: o kanban
não pode abrir vazio.

Revision ID: 88728a91f918
Revises: 1dcac039656c
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '88728a91f918'
down_revision: Union[str, Sequence[str], None] = '1dcac039656c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conexao = op.get_bind()

    # 1 · Nullable primeiro — a tabela já tem as colunas globais.
    op.add_column('tarefa_coluna', sa.Column('projeto_id', sa.Integer(), nullable=True))
    op.create_index(
        op.f('ix_tarefa_coluna_projeto_id'), 'tarefa_coluna', ['projeto_id'], unique=False
    )
    # ⚠ A unicidade GLOBAL de `chave` tem que cair ANTES dos clones: cada
    # projeto vai ter o seu "a_fazer", e com ela de pé o primeiro INSERT já
    # bate em "Duplicate entry".
    # 'chave' é o nome que o MySQL dá sozinho a um UNIQUE sem nome explícito
    # (nomeia pela coluna) — o Postgres nomeia diferente, então busca o nome
    # de verdade em vez de chutar.
    _nome_unique_chave = next(
        uq['name'] for uq in sa.inspect(conexao).get_unique_constraints('tarefa_coluna')
        if uq['column_names'] == ['chave']
    )
    op.drop_constraint(_nome_unique_chave, 'tarefa_coluna', type_='unique')

    globais = conexao.execute(
        sa.text(
            "SELECT id, chave, nome, cor, ordem, encerra_tarefa "
            "FROM tarefa_coluna WHERE projeto_id IS NULL ORDER BY ordem, id"
        )
    ).fetchall()
    projetos = conexao.execute(sa.text("SELECT id FROM projeto")).fetchall()

    # 2 e 3 · Uma cópia por projeto, e as tarefas apontando para a própria.
    for (projeto_id,) in projetos:
        for antiga in globais:
            conexao.execute(
                sa.text(
                    "INSERT INTO tarefa_coluna "
                    "(projeto_id, chave, nome, cor, ordem, encerra_tarefa) "
                    "VALUES (:p, :chave, :nome, :cor, :ordem, :encerra)"
                ),
                {
                    "p": projeto_id,
                    "chave": antiga.chave,
                    "nome": antiga.nome,
                    "cor": antiga.cor,
                    "ordem": antiga.ordem,
                    "encerra": antiga.encerra_tarefa,
                },
            )
            # `.lastrowid` é MySQL/SQLite — o Postgres não tem "last insert
            # id" de cursor. Busca de volta pelo par (projeto, chave), que é
            # único dentro deste loop.
            nova_id = conexao.execute(
                sa.text("SELECT id FROM tarefa_coluna WHERE projeto_id = :p AND chave = :chave"),
                {"p": projeto_id, "chave": antiga.chave},
            ).scalar()
            conexao.execute(
                sa.text(
                    "UPDATE tarefa SET coluna_id = :nova "
                    "WHERE projeto_id = :p AND coluna_id = :antiga"
                ),
                {"nova": nova_id, "p": projeto_id, "antiga": antiga.id},
            )

    # 4 · As globais já não têm tarefa apontando para elas.
    conexao.execute(sa.text("DELETE FROM tarefa_coluna WHERE projeto_id IS NULL"))

    # 5 · Agora sim.
    op.alter_column(
        'tarefa_coluna', 'projeto_id', existing_type=sa.Integer(), nullable=False
    )
    op.create_foreign_key(
        'fk_coluna_projeto', 'tarefa_coluna', 'projeto', ['projeto_id'], ['id']
    )
    # A unicidade volta, agora por projeto.
    op.create_unique_constraint(
        'uq_coluna_projeto_chave', 'tarefa_coluna', ['projeto_id', 'chave']
    )


def downgrade() -> None:
    """⚠ Volta colapsa os boards: sobra um conjunto só, e as tarefas de todos
    os projetos são repontadas para ele. Colunas customizadas de projetos
    diferentes com o mesmo nome viram uma só."""
    conexao = op.get_bind()

    op.drop_constraint('uq_coluna_projeto_chave', 'tarefa_coluna', type_='unique')
    op.drop_constraint('fk_coluna_projeto', 'tarefa_coluna', type_='foreignkey')
    op.alter_column(
        'tarefa_coluna', 'projeto_id', existing_type=sa.Integer(), nullable=True
    )

    linhas = conexao.execute(
        sa.text("SELECT id, chave, nome FROM tarefa_coluna ORDER BY projeto_id, ordem")
    ).fetchall()
    vistos: dict = {}
    for linha in linhas:
        marca = linha.chave or linha.nome
        if marca in vistos:
            conexao.execute(
                sa.text("UPDATE tarefa SET coluna_id = :fica WHERE coluna_id = :sai"),
                {"fica": vistos[marca], "sai": linha.id},
            )
            conexao.execute(
                sa.text("DELETE FROM tarefa_coluna WHERE id = :id"), {"id": linha.id}
            )
        else:
            vistos[marca] = linha.id

    conexao.execute(sa.text("UPDATE tarefa_coluna SET projeto_id = NULL"))
    op.drop_index(op.f('ix_tarefa_coluna_projeto_id'), table_name='tarefa_coluna')
    op.drop_column('tarefa_coluna', 'projeto_id')
    op.create_unique_constraint('chave', 'tarefa_coluna', ['chave'])
