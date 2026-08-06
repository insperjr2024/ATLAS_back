from sqlalchemy import Column, Integer, String, Boolean
from src.database.database import Base


class CargoModel(Base):
    """As 10 permissões da plataforma, uma caixa por ação do §3.

    São exatamente as 10 linhas da tabela do briefing. Antes elas eram
    hardcoded por `posicao` (`require_gestao`, `require_lideranca`,
    `require_diretor` direto nas rotas); agora a posição só define o PADRÃO com
    que cada cargo nasce, e quem decide em runtime é a caixa.

    O que não está na tabela continua por posição — ver `authorization.py`.
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
    # 6. Aprovar reajuste de cronograma
    pode_aprovar_reajuste = Column(Boolean, default=False, nullable=False)
    # 7. Criar tarefa
    pode_criar_tarefa = Column(Boolean, default=False, nullable=False)
    # 8. Mover e editar tarefa
    pode_mover_editar_tarefa = Column(Boolean, default=False, nullable=False)
    # 9. Ver os próprios projetos
    pode_ver_proprios_projetos = Column(Boolean, default=False, nullable=False)
    # 10. Monitoramento e alocação
    pode_ver_monitoramento = Column(Boolean, default=False, nullable=False)
