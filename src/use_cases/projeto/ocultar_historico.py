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
        # ⚠ `datetime.now()`, não `utcnow()`: o corte é comparado com carimbos
        # gravados por `datetime.now()` (hora local) no resto do sistema —
        # `registrado_em`, `alterado_em`, `criado_em`. Marcando o corte em UTC,
        # ele nascia TRÊS HORAS no futuro, e tudo que fosse registrado nas
        # horas seguintes ficava "antes do corte" e sumia da timeline.
        #
        # Na prática: limpar o histórico e escrever uma justificativa logo
        # depois devolvia uma timeline vazia — a nota entrava no banco e não
        # aparecia em lugar nenhum.
        return self.repository.update(projeto_id, historico_oculto_ate=datetime.now())


class MostrarHistoricoCompletoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int):
        return self.repository.update(projeto_id, historico_oculto_ate=None)
