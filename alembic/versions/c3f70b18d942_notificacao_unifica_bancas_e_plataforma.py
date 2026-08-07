"""notificacao_unifica_bancas_e_plataforma

Revision ID: c3f70b18d942
Revises: 8bf1f608bfea
Create Date: 2026-08-06 10:20:00.000000

A tabela `notificacao` nasceu na `73fcb381a784` para os avisos de banca (§8):
`mensagem` + `banca_id` + `lida`. Os alertas da plataforma (§6.6) precisam de
mais: distinguir tipo, separar evento de condição, deduplicar e guardar QUANDO
foi lida. Em vez de uma segunda tabela — e um segundo sino —, esta migration
alarga a que já existe.

O mapeamento:

    mensagem  → titulo
    lida      → lida_em   (o timestamp responde "quando", o booleano não)
    banca_id  → payload["banca_id"]

As colunas entram NULLABLE, os dados existentes são convertidos, e só então
elas viram NOT NULL. Fazer o contrário quebraria em qualquer banco que já
tenha notificação gravada — que é o caso de todo mundo que rodou a main.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f70b18d942'
down_revision: Union[str, Sequence[str], None] = '8bf1f608bfea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIPOS = (
    'alocado_em_projeto',
    'entrega_registrada',
    'escalacao_banca',
    'troca_banca',
    'avaliacao_pendente',
    'banca_aviso',
    'kickoff_pendente',
    'tarefa_vencida',
    'banca_nao_marcada',
    'projeto_sem_reuniao',
    'banca_hoje',
)


def _dropar_fk_de(bind, tabela: str, coluna: str) -> None:
    """Remove a foreign key que sai de `tabela.coluna`, seja qual for o nome.

    Sem isto a migration dependeria de `notificacao_ibfk_1` — um nome que o
    MySQL atribui por ordem de criação e que muda se alguém mexer nas
    constraints antes daqui.
    """
    for fk in sa.inspect(bind).get_foreign_keys(tabela):
        if coluna in fk['constrained_columns'] and fk.get('name'):
            op.drop_constraint(fk['name'], tabela, type_='foreignkey')


def _criar_indice_se_faltar(bind, tabela: str, nome: str, colunas: list) -> None:
    if nome not in {i['name'] for i in sa.inspect(bind).get_indexes(tabela)}:
        op.create_index(nome, tabela, colunas)


def upgrade() -> None:
    """Upgrade schema."""
    tipo_enum = sa.Enum(*TIPOS, name='tipo_notificacao')
    origem_enum = sa.Enum('evento', 'condicao', name='origem_notificacao')
    tipo_enum.create(op.get_bind(), checkfirst=True)
    origem_enum.create(op.get_bind(), checkfirst=True)

    # 1. `mensagem` vira `titulo` — mesmo tipo, só o nome muda.
    op.alter_column(
        'notificacao', 'mensagem',
        new_column_name='titulo',
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )

    # 1b. `criado_em` ganha default no banco. A versão de bancas não tinha:
    #     `notificar()` passava `datetime.now()` a cada chamada. Agora quem
    #     grava é `registrar()`, que deixa o carimbo para o banco — sem este
    #     default o INSERT falha com "Field 'criado_em' doesn't have a default".
    op.alter_column(
        'notificacao', 'criado_em',
        existing_type=sa.DateTime(),
        server_default=sa.text('now()'),
        existing_nullable=False,
    )

    # 2. As colunas novas, todas nullable por enquanto.
    op.add_column('notificacao', sa.Column('tipo', tipo_enum, nullable=True))
    op.add_column('notificacao', sa.Column('origem', origem_enum, nullable=True))
    op.add_column('notificacao', sa.Column('corpo', sa.String(length=500), nullable=True))
    op.add_column('notificacao', sa.Column('projeto_id', sa.Integer(), nullable=True))
    op.add_column('notificacao', sa.Column('payload', sa.JSON(), nullable=True))
    op.add_column('notificacao', sa.Column('chave_dedup', sa.String(length=120), nullable=True))
    op.add_column('notificacao', sa.Column('lida_em', sa.DateTime(), nullable=True))
    op.add_column('notificacao', sa.Column('email_enviado_em', sa.DateTime(), nullable=True))

    # 3. Converte o que já está gravado. Toda linha existente é de banca — a
    #    tabela ainda não tinha outro produtor.
    op.execute("UPDATE notificacao SET tipo = 'banca_aviso', origem = 'evento'")
    op.execute("UPDATE notificacao SET lida_em = criado_em WHERE lida = true")
    # `JSON_OBJECT` é MySQL; o equivalente do Postgres é `json_build_object`.
    funcao_json = "json_build_object" if op.get_bind().dialect.name == 'postgresql' else "JSON_OBJECT"
    op.execute(
        f"UPDATE notificacao SET payload = {funcao_json}('banca_id', banca_id) "
        "WHERE banca_id IS NOT NULL"
    )
    # A chave precisa ser única por usuário e estas linhas não têm identidade
    # natural — o id serve, e o prefixo deixa claro que vieram da conversão.
    op.execute("UPDATE notificacao SET chave_dedup = CONCAT('legado:', id)")

    # 4. Agora que estão preenchidas, viram obrigatórias.
    op.alter_column('notificacao', 'tipo', existing_type=tipo_enum, nullable=False)
    op.alter_column('notificacao', 'origem', existing_type=origem_enum, nullable=False)
    op.alter_column(
        'notificacao', 'chave_dedup', existing_type=sa.String(length=120), nullable=False
    )

    # 5. As colunas substituídas saem, junto com a FK de `banca_id`.
    #    O nome da FK é descoberto, não chutado: a `73fcb381a784` não deu nome
    #    a ela, então quem nomeou foi o MySQL (`notificacao_ibfk_N`) — e a
    #    numeração depende da ordem em que as constraints foram criadas.
    _dropar_fk_de(op.get_bind(), 'notificacao', 'banca_id')
    op.drop_column('notificacao', 'banca_id')
    op.drop_column('notificacao', 'lida')

    # 6. Índices e o anti-spam do §6.6, no banco e não só no código: duas
    #    passadas concorrentes não conseguem inserir o mesmo alerta duas vezes.
    # `checkfirst` à mão: o downgrade não remove o índice de `usuario_id` (o
    # MySQL precisa dele para a FK), então um ciclo downgrade→upgrade encontra
    # ele já criado e o CREATE INDEX cru estouraria.
    _criar_indice_se_faltar(op.get_bind(), 'notificacao', 'ix_notificacao_usuario_id', ['usuario_id'])
    _criar_indice_se_faltar(op.get_bind(), 'notificacao', 'ix_notificacao_projeto_id', ['projeto_id'])
    op.create_unique_constraint(
        'uq_notificacao_usuario_chave', 'notificacao', ['usuario_id', 'chave_dedup']
    )
    op.create_foreign_key(
        'fk_notificacao_projeto', 'notificacao', 'projeto', ['projeto_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # A FK sai ANTES do índice que a sustenta — o MySQL recusa dropar um
    # índice que ainda serve de apoio a uma foreign key.
    op.drop_constraint('fk_notificacao_projeto', 'notificacao', type_='foreignkey')
    op.drop_index(op.f('ix_notificacao_projeto_id'), table_name='notificacao')
    op.drop_constraint('uq_notificacao_usuario_chave', 'notificacao', type_='unique')
    # ⚠ `ix_notificacao_usuario_id` NÃO é removido de propósito: a FK de
    # `usuario_id` continua existindo e o MySQL exige um índice sustentando
    # ela. Tentar dropar aqui dava
    # "Cannot drop index: needed in a foreign key constraint" — e, como o DDL
    # do MySQL não é transacional, o downgrade morria no meio, deixando a
    # tabela sem a unique e sem a FK de projeto. Um índice a mais é inofensivo.

    op.add_column('notificacao', sa.Column('lida', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('notificacao', sa.Column('banca_id', sa.Integer(), nullable=True))
    op.execute("UPDATE notificacao SET lida = 1 WHERE lida_em IS NOT NULL")
    # ⚠ As linhas do §6.6 (kickoff, tarefa vencida…) não têm banca e ficam com
    # `banca_id` nulo. A volta não é sem perda: `tipo`, `payload` e `origem`
    # somem, e com eles a distinção entre evento e condição.
    op.execute(
        "UPDATE notificacao SET banca_id = JSON_EXTRACT(payload, '$.banca_id') "
        "WHERE payload IS NOT NULL AND JSON_EXTRACT(payload, '$.banca_id') IS NOT NULL"
    )
    op.create_foreign_key(
        'notificacao_ibfk_1', 'notificacao', 'banca', ['banca_id'], ['id'], ondelete='CASCADE'
    )

    for coluna in ('email_enviado_em', 'lida_em', 'chave_dedup', 'payload', 'projeto_id',
                   'corpo', 'origem', 'tipo'):
        op.drop_column('notificacao', coluna)

    op.alter_column(
        'notificacao', 'titulo',
        new_column_name='mensagem',
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        'notificacao', 'criado_em',
        existing_type=sa.DateTime(),
        server_default=None,
        existing_nullable=False,
    )
    sa.Enum(name='tipo_notificacao').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='origem_notificacao').drop(op.get_bind(), checkfirst=True)
