from sqlalchemy import Boolean, Column, Enum, Integer
from src.database.database import Base


class PosicaoPermissaoModel(Base):
    """As permissões da plataforma, uma caixa por ação — POR POSIÇÃO.

    Substitui `cargo` (removido em 2026-08-07): eram duas dimensões de
    permissão convivendo (posição decidia o recorte de visão, cargo decidia
    o resto), e a distinção não sobreviveu ao uso real — cargo só criava
    combinação estranha (ex.: "Admin" que não amplia visão de projeto
    nenhuma) sem servir pra delegar de verdade. Só 4 linhas, uma por posição,
    sem CRUD de criar/apagar linha — só editar as caixas.

    Mesmas 13 caixas que `cargo` tinha: as 9 da tabela do §3 do briefing, as
    3 extensões (Avaliação de Desempenho, formulários dela, Configurações) e
    `pode_ver_todos_projetos` (2026-08-07) — a única que muda QUAIS projetos
    aparecem; as outras só ligam/desligam funcionalidade.
    """

    __tablename__ = "posicao_permissao"

    id = Column(Integer, primary_key=True, index=True)
    posicao = Column(
        Enum("diretor", "gerente", "coordenador", "consultor", name="posicao_permissao_posicao"),
        nullable=False,
        unique=True,
    )

    # 1. Criar projeto e alocar equipe
    pode_criar_projeto = Column(Boolean, default=False, nullable=False)
    # 2. Editar a equipe de um projeto
    pode_editar_equipe = Column(Boolean, default=False, nullable=False)
    # 3. Gerir membros (posição e status)
    pode_gerir_membros = Column(Boolean, default=False, nullable=False)
    # 4. Marcar kickoff e data de entrega
    pode_marcar_kickoff = Column(Boolean, default=False, nullable=False)
    # 5. Definir cronograma por escopo (etapas, banca)
    pode_definir_cronograma = Column(Boolean, default=False, nullable=False)
    # 7. Criar tarefa
    pode_criar_tarefa = Column(Boolean, default=False, nullable=False)
    # 8. Mover e editar tarefa
    pode_mover_editar_tarefa = Column(Boolean, default=False, nullable=False)
    # 9. Ver os próprios projetos
    pode_ver_proprios_projetos = Column(Boolean, default=False, nullable=False)
    # 10. Monitoramento e alocação
    pode_ver_monitoramento = Column(Boolean, default=False, nullable=False)

    # Extensões além das 10 do §3.
    pode_administrar_desempenho = Column(Boolean, default=False, nullable=False)
    pode_editar_formularios_desempenho = Column(Boolean, default=False, nullable=False)
    pode_administrar_configuracoes = Column(Boolean, default=False, nullable=False)

    # A única que muda QUAIS projetos aparecem (ver docstring da classe).
    pode_ver_todos_projetos = Column(Boolean, default=False, nullable=False)
