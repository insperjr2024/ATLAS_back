"""bdr e coordenador de vendas por cargo

Revision ID: bb255f970798
Revises: b74e1c843933
Create Date: 2026-09-16 00:00:00.000000

`usuario.coordenador_vendas` e `usuario.bdr` eram dois booleanos soltos, sem
ligação nenhuma com o resto do sistema de permissões — criar um cargo novo
não tinha como herdar esse comportamento nem mostrar que o tinha.

1. `posicao_permissao` ganha duas caixas: `pode_responsavel_por_vendas`
   (aparece na lista "quem vendeu o projeto") e `pode_coordenar_vendas`
   (continua liderança, mas não fecha `min_lideranca`/`min_membros` da frente
   em que está cadastrado — o antigo `eh_lideranca_sem_frente`).

2. "Coordenador de vendas" vira posição de verdade: o cargo "vendas" (já
   existia, em branco) recebe as DUAS caixas novas MAIS as permissões que
   `coordenador` já tinha (kickoff, cronograma, tarefa, ver próprios
   projetos) — sem isso, migrar os 4 coordenadores de vendas de hoje pra este
   cargo tiraria acesso que eles já tinham.

3. `usuario` ganha `cargo_extra`: a ÚNICA situação em que a plataforma deixa
   a pessoa acumular duas posições — a principal (sempre "consultor" na
   prática) e um cargo "bdr" opcional. Criado (se não existir) com só
   `pode_responsavel_por_vendas` ligada.

4. Dado migrado (produção, checado antes de escrever esta migration):
   - 4 usuários com `coordenador_vendas=true` (todos `posicao=coordenador`)
     viram `posicao='vendas'`.
   - 8 usuários com `bdr=true` (todos `posicao=consultor`) ganham
     `cargo_extra='bdr'`, mantendo `posicao='consultor'`.

5. `usuario.bdr` e `usuario.coordenador_vendas` saem — substituídos pelos
   dois campos acima.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb255f970798'
down_revision: Union[str, Sequence[str], None] = 'b74e1c843933'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: As caixas que `coordenador` já tinha — copiadas pro cargo "vendas" pra
#: não regredir o acesso dos 4 coordenadores de vendas de hoje.
PERMISSOES_DE_COORDENADOR = (
    "pode_marcar_kickoff",
    "pode_definir_cronograma",
    "pode_criar_tarefa",
    "pode_mover_editar_tarefa",
    "pode_ver_proprios_projetos",
)


def upgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_responsavel_por_vendas", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_coordenar_vendas", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "usuario",
        sa.Column("cargo_extra", sa.String(length=50), nullable=True),
    )
    op.create_foreign_key(
        "fk_usuario_cargo_extra_posicao_permissao",
        "usuario",
        "posicao_permissao",
        ["cargo_extra"],
        ["posicao"],
    )

    bind = op.get_bind()

    # 2. "vendas" herda o que `coordenador` já tinha, mais as duas caixas
    # novas — o cargo existia em branco (criado manualmente antes desta
    # migration, ver a conversa que pediu a feature).
    colunas = ", ".join(f"{c} = true" for c in PERMISSOES_DE_COORDENADOR)
    bind.execute(
        sa.text(
            f"UPDATE posicao_permissao SET {colunas}, "
            "pode_coordenar_vendas = true, pode_responsavel_por_vendas = true "
            "WHERE posicao = 'vendas'"
        )
    )

    # 3. o cargo "bdr" — só a caixa de vendas, criado se ainda não existir.
    ja_existe_bdr = bind.execute(
        sa.text("SELECT 1 FROM posicao_permissao WHERE posicao = 'bdr'")
    ).first()
    if not ja_existe_bdr:
        bind.execute(
            sa.text(
                "INSERT INTO posicao_permissao (posicao, nome, e_padrao, "
                "pode_criar_projeto, pode_editar_equipe, pode_gerir_membros, "
                "pode_marcar_kickoff, pode_definir_cronograma, pode_criar_tarefa, "
                "pode_mover_editar_tarefa, pode_ver_proprios_projetos, pode_ver_monitoramento, "
                "pode_administrar_desempenho, pode_editar_formularios_desempenho, "
                "pode_administrar_configuracoes, pode_ver_dashboard_bancas, "
                "pode_ver_historico_projetos, pode_ver_tarefas_gerais, pode_ver_cronogramas_gerais, "
                "pode_configurar_colunas, pode_aprovar_pedidos, pode_administrar_permissoes, "
                "pode_gerir_calendarios_base, pode_ver_todos_projetos, "
                "pode_responsavel_por_vendas, pode_coordenar_vendas) "
                "VALUES ('bdr', 'BDR', false, "
                "false, false, false, false, false, false, false, false, false, "
                "false, false, false, false, false, false, false, false, false, "
                "false, false, false, true, false)"
            )
        )

    # 4. move os 4 coordenadores de vendas pra posição própria — REESCREVE
    # `posicao` (era 'coordenador'), igual `TransferirDiretoriaUseCase` faz
    # numa promoção normal.
    bind.execute(sa.text("UPDATE usuario SET posicao = 'vendas' WHERE coordenador_vendas = true"))

    # 5. os 8 BDR ganham o cargo EXTRA, sem mexer na posição principal
    # (fica 'consultor').
    bind.execute(sa.text("UPDATE usuario SET cargo_extra = 'bdr' WHERE bdr = true"))

    op.drop_column("usuario", "bdr")
    op.drop_column("usuario", "coordenador_vendas")


def downgrade() -> None:
    op.add_column("usuario", sa.Column("coordenador_vendas", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("usuario", sa.Column("bdr", sa.Boolean(), nullable=False, server_default=sa.false()))

    bind = op.get_bind()
    # ⚠ Restaura o SINAL, não a posição anterior — "vendas" volta a ser só
    # mais um cargo (a `posicao` fica como está, não volta a 'coordenador').
    bind.execute(sa.text("UPDATE usuario SET coordenador_vendas = true WHERE posicao = 'vendas'"))
    bind.execute(sa.text("UPDATE usuario SET bdr = true WHERE cargo_extra = 'bdr'"))

    op.drop_constraint("fk_usuario_cargo_extra_posicao_permissao", "usuario", type_="foreignkey")
    op.drop_column("usuario", "cargo_extra")
    op.drop_column("posicao_permissao", "pode_coordenar_vendas")
    op.drop_column("posicao_permissao", "pode_responsavel_por_vendas")
