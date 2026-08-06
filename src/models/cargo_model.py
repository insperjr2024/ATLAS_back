from sqlalchemy import Column, Integer, String, Boolean
from src.database.database import Base


class CargoModel(Base):
    """As permissões da plataforma, uma caixa por ação.

    9 das 10 são as linhas da tabela do §3 do briefing — "aprovar reajuste"
    saiu em 2026-08-06 junto com a feature de reajuste de cronograma, que foi
    removida a pedido do usuário. Antes elas eram hardcoded por `posicao`
    (`require_gestao`, `require_lideranca`, `require_diretor` direto nas
    rotas); agora a posição só define o PADRÃO com que cada cargo nasce, e
    quem decide em runtime é a caixa.

    As 4 seguintes (Avaliação de Desempenho, formulários dela, Núcleo,
    Configurações) não estão no §3 — nasceram travadas só por posição e
    viraram caixa a pedido explícito do usuário (2026-08-06), pro mesmo motivo
    das 9: dar pra delegar sem precisar tornar alguém "diretor" inteiro.
    """

    __tablename__ = "cargo"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)

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

    # Extensão além das 10 do §3 (ver docstring da classe).
    pode_administrar_desempenho = Column(Boolean, default=False, nullable=False)
    pode_editar_formularios_desempenho = Column(Boolean, default=False, nullable=False)
    pode_ver_nucleo = Column(Boolean, default=False, nullable=False)
    pode_administrar_configuracoes = Column(Boolean, default=False, nullable=False)
