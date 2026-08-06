from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository


class OcultarHistoricoUseCase:
    """"Limpar histórico" (§4) não apaga linha nenhuma de
    `projeto_status_historico` — só marca 'agora' como corte de exibição da
    timeline. As linhas anteriores ao corte continuam no banco, porque
    alimentam a contagem de dias (§5.4); só saem da tela."""

    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int):
        return self.repository.update(projeto_id, historico_oculto_ate=datetime.utcnow())


class MostrarHistoricoCompletoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int):
        return self.repository.update(projeto_id, historico_oculto_ate=None)
