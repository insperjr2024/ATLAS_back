"""Ajuda as migrations que redefinem um ENUM a rodar em MySQL e Postgres.

No MySQL, `ALTER TABLE ... MODIFY COLUMN ... ENUM(...)` redefine o conjunto de
valores inteiro numa tacada só — é o que `op.alter_column(type_=sa.Enum(...))`
gera. No Postgres um ENUM é um `TYPE` à parte, e `ALTER TYPE` só sabe
ADICIONAR valor (`ADD VALUE`) — não existe `DROP VALUE`. Pra tirar um valor
(ou pra manter as duas migrations com o mesmo formato, adicionando ou não),
o jeito genérico é: type novo com o conjunto final, troca a coluna pra ele,
apaga o velho.
"""

import sqlalchemy as sa


def redefinir_enum_postgres(op, tabela: str, coluna: str, nome_tipo: str, valores_novos):
    """Só faz algo se o bind for Postgres — no MySQL quem chamou já resolveu
    com `op.alter_column` antes de vir aqui."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    tipo_tmp = f"{nome_tipo}_novo"
    sa.Enum(*valores_novos, name=tipo_tmp).create(bind, checkfirst=True)
    op.execute(
        f'ALTER TABLE {tabela} ALTER COLUMN {coluna} '
        f'TYPE {tipo_tmp} USING {coluna}::text::{tipo_tmp}'
    )
    op.execute(f"DROP TYPE {nome_tipo}")
    op.execute(f"ALTER TYPE {tipo_tmp} RENAME TO {nome_tipo}")


def nome_da_fk(op, tabela: str, coluna: str):
    """O nome real da FK daquela coluna, perguntando ao banco.

    ⚠ **Nome de FK não é portável.** O Postgres gera
    `configuracao_cargo_padrao_id_fkey`; o MySQL gera `configuracao_ibfk_1`.
    Uma migration que crava o nome de um dos dois quebra no outro com 1091
    ("Can't DROP ...; check that column/key exists") — foi o que aconteceu com
    `03ea41a273d0` ao rodar em MySQL.

    Devolve `None` quando não há FK naquela coluna, para o chamador poder
    simplesmente pular o `drop_constraint` em vez de estourar.
    """
    import sqlalchemy as sa

    for fk in sa.inspect(op.get_bind()).get_foreign_keys(tabela):
        if coluna in fk["constrained_columns"]:
            return fk["name"]
    return None
