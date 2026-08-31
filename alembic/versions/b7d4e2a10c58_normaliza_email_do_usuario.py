"""normaliza_email_do_usuario

Põe todo `usuario.email_insper` em minúsculas e sem espaço nas pontas.

O endereço de e-mail não distingue maiúscula de minúscula, mas o `=` do
Postgres distingue. Dez contas cadastradas com a inicial maiúscula
("Fulano@al.insper.edu.br", como o formulário de pré-cadastro capitaliza)
recebiam a senha provisória e nunca conseguiam entrar: a pessoa digitava o
endereço em minúsculo, a busca não achava ninguém e o login respondia "Email ou
senha incorretos". O "esqueci minha senha" saía calado, sem mandar e-mail.

Não aparecia no MySQL, o banco anterior, cuja collation padrão compara sem
caixa. A mudança para o Supabase trocou essa regra sem que o código mudasse.

Esta migration cuida do dado que já existe; o código (`UsuarioRepository`)
passa a normalizar na escrita e a comparar sem caixa na leitura, então o
problema não volta por cadastro novo.

Conferido antes de escrever: zero e-mails que colidam depois de normalizados,
ou seja, o UPDATE não esbarra na unique de `email_insper`.

Revision ID: b7d4e2a10c58
Revises: f2b6e1c94a07
Create Date: 2026-08-24 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d4e2a10c58'
down_revision: Union[str, Sequence[str], None] = 'f2b6e1c94a07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # O WHERE evita reescrever as ~57 linhas que já estão normalizadas.
    op.execute(
        sa.text(
            "UPDATE usuario SET email_insper = LOWER(TRIM(email_insper)) "
            "WHERE email_insper <> LOWER(TRIM(email_insper))"
        )
    )


def downgrade() -> None:
    """Downgrade schema.

    Sem volta: a caixa original não é recuperável depois do UPDATE, e recuperá-la
    não teria valor nenhum -- ela é justamente o defeito que esta migration
    conserta.
    """
    pass
