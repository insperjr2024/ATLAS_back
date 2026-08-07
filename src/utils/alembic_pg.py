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
