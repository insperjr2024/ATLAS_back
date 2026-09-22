"""Contratos Fase 1: tabelas, permissões e status da integração

Revision ID: 343e1f0be526
Revises: bb255f970798
Create Date: 2026-09-16

Schema-only, acompanha os models de `c3bc96f` (Fase 1 de dados da integração
com a antiga plataforma Contratos):

1. `contrato_em_elaboracao` entra no enum `status_projeto` — o projeto nasce
   aqui quando alguém abre o Contrato de Prestação de Serviços na aba
   Contratos, antes de existir venda de verdade (ver o comentário em
   `projeto_model.py`). Postgres não deixa apagar valor de enum sem recriar o
   tipo inteiro — mesma trava de `a2c8f61de930`, mesma solução
   (`autocommit_block` + `ADD VALUE IF NOT EXISTS`, fora da transação).

2. Seis caixas novas em `posicao_permissao`, todas `false` para todo mundo:
   nenhuma tela ainda lê nenhuma delas — ligar quem tem cada uma (Jurídico,
   coordenador etc.) é decisão de quando o cargo Jurídico e as rotas que os
   usam existirem, não desta migration.

3. As cinco tabelas novas do domínio jurídico (`documento_contratual` e o que
   pendura nela) e a linha única de `identidade_institucional`, semeada com
   os valores atuais (mesmos `server_default` do model) para a tela de
   configuração já abrir preenchida.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "343e1f0be526"
down_revision: Union[str, Sequence[str], None] = "bb255f970798"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUNAS_PERMISSAO = [
    "pode_gerar_documento_juridico",
    "pode_editar_documento_juridico",
    "pode_marcar_documento_assinado",
    "pode_ver_repositorio_contratos",
    "pode_importar_documento_antigo",
    "pode_solicitar_tep",
]


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "ALTER TYPE status_projeto ADD VALUE IF NOT EXISTS "
                "'contrato_em_elaboracao' BEFORE 'vendido'"
            )

    for coluna in COLUNAS_PERMISSAO:
        op.add_column(
            "posicao_permissao",
            sa.Column(coluna, sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    op.create_table(
        "documento_contratual",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("projeto_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=40), nullable=False,
            server_default="aguardando_preenchimento",
        ),
        sa.Column("dados", sa.JSON(), nullable=True),
        sa.Column("confirmado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("gestao_id", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column(
            "atualizado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(["gestao_id"], ["semestre.id"]),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("projeto_id", "tipo", name="uq_documento_contratual_projeto_tipo"),
    )
    op.create_index(
        op.f("ix_documento_contratual_id"), "documento_contratual", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_documento_contratual_projeto_id"),
        "documento_contratual",
        ["projeto_id"],
        unique=False,
    )

    op.create_table(
        "documento_contratual_versao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("documento_id", sa.Integer(), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status_arquivo", sa.String(length=20), nullable=False, server_default="rascunho"
        ),
        sa.Column("gestao_id", sa.Integer(), nullable=True),
        sa.Column("docx_path", sa.String(length=500), nullable=False),
        sa.Column("pdf_path", sa.String(length=500), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("arquivado_em", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["documento_id"], ["documento_contratual.id"]),
        sa.ForeignKeyConstraint(["gestao_id"], ["semestre.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_documento_contratual_versao_id"),
        "documento_contratual_versao",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_documento_contratual_versao_documento_id"),
        "documento_contratual_versao",
        ["documento_id"],
        unique=False,
    )

    op.create_table(
        "token_aprovacao_contratual",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("documento_id", sa.Integer(), nullable=False),
        sa.Column("versao_id", sa.Integer(), nullable=False),
        sa.Column("usado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["documento_id"], ["documento_contratual.id"]),
        sa.ForeignKeyConstraint(["versao_id"], ["documento_contratual_versao.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        op.f("ix_token_aprovacao_contratual_id"),
        "token_aprovacao_contratual",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_token_aprovacao_contratual_token"),
        "token_aprovacao_contratual",
        ["token"],
        unique=False,
    )
    op.create_index(
        op.f("ix_token_aprovacao_contratual_documento_id"),
        "token_aprovacao_contratual",
        ["documento_id"],
        unique=False,
    )

    op.create_table(
        "solicitacao_alteracao_contratual",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("documento_id", sa.Integer(), nullable=False),
        sa.Column("versao_id", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("trechos", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pendente"),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["documento_id"], ["documento_contratual.id"]),
        sa.ForeignKeyConstraint(["versao_id"], ["documento_contratual_versao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_solicitacao_alteracao_contratual_id"),
        "solicitacao_alteracao_contratual",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_solicitacao_alteracao_contratual_documento_id"),
        "solicitacao_alteracao_contratual",
        ["documento_id"],
        unique=False,
    )

    op.create_table(
        "identidade_institucional",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "presidente_nome", sa.String(length=255), nullable=False,
            server_default="JOSÉ ROBERTO SARAIVA COSTA JÚNIOR",
        ),
        sa.Column(
            "presidente_cpf", sa.String(length=20), nullable=False,
            server_default="042.777.813-14",
        ),
        sa.Column(
            "presidente_rg", sa.String(length=30), nullable=False, server_default="688539531"
        ),
        sa.Column(
            "presidente_orgao_emissor", sa.String(length=20), nullable=False,
            server_default="SSP/SP",
        ),
        sa.Column(
            "presidente_endereco", sa.String(length=500), nullable=False,
            server_default="Rua Casa do Ator, nº 829, Vila Olímpia, CEP: 4546003, São Paulo/SP",
        ),
        sa.Column(
            "presidente_estado_civil", sa.String(length=30), nullable=False,
            server_default="solteiro",
        ),
        sa.Column(
            "presidente_nacionalidade", sa.String(length=30), nullable=False,
            server_default="brasileiro",
        ),
        sa.Column(
            "presidente_profissao", sa.String(length=100), nullable=False,
            server_default="estudante",
        ),
        sa.Column("presidente_email", sa.String(length=255), nullable=True),
        sa.Column("presidente_telefone", sa.String(length=30), nullable=True),
        sa.Column(
            "testemunha1_nome", sa.String(length=255), nullable=False,
            server_default="Pedro de Paula Eduardo",
        ),
        sa.Column(
            "testemunha1_cpf", sa.String(length=20), nullable=False,
            server_default="495.388.168-03",
        ),
        sa.Column("testemunha1_email", sa.String(length=255), nullable=True),
        sa.Column("testemunha1_telefone", sa.String(length=30), nullable=True),
        sa.Column(
            "testemunha2_nome", sa.String(length=255), nullable=False,
            server_default="Matias Bordalo Amaro Krueder",
        ),
        sa.Column(
            "testemunha2_cpf", sa.String(length=20), nullable=False,
            server_default="477.886.678-97",
        ),
        sa.Column("testemunha2_email", sa.String(length=255), nullable=True),
        sa.Column("testemunha2_telefone", sa.String(length=30), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Linha única (id=1) — os demais campos pegam o `server_default` acima,
    # a mesma identidade institucional vigente hoje.
    op.execute("INSERT INTO identidade_institucional (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("identidade_institucional")
    op.drop_table("solicitacao_alteracao_contratual")
    op.drop_table("token_aprovacao_contratual")
    op.drop_table("documento_contratual_versao")
    op.drop_table("documento_contratual")

    for coluna in COLUNAS_PERMISSAO:
        op.drop_column("posicao_permissao", coluna)

    # `contrato_em_elaboracao` fica no tipo — mesma razão de `a2c8f61de930`:
    # Postgres não remove valor de enum sem recriar o tipo inteiro, e nenhum
    # projeto passa a usá-lo sozinho por ele continuar ali.
