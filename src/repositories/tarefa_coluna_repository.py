from typing import List

from src.models.tarefa_coluna_model import TarefaColunaModel
from src.repositories.base_repository import BaseRepository


class TarefaColunaRepository(BaseRepository[TarefaColunaModel]):
    model = TarefaColunaModel

    def listar(self, projeto_id: int) -> List[TarefaColunaModel]:
        """As colunas DE UM projeto. Cada um tem o seu fluxo."""
        return (
            self.db.query(TarefaColunaModel)
            .filter(TarefaColunaModel.projeto_id == projeto_id)
            .order_by(TarefaColunaModel.ordem, TarefaColunaModel.id)
            .all()
        )

    def listar_todas(self) -> List[TarefaColunaModel]:
        """Todas, de todos os projetos — o monitoramento agrega vários e não
        pode fazer uma consulta por projeto."""
        return self.db.query(TarefaColunaModel).all()

    def proxima_ordem(self, projeto_id: int) -> int:
        colunas = self.listar(projeto_id)
        return max((c.ordem for c in colunas), default=-1) + 1

    def primeira(self, projeto_id: int):
        """A coluna onde a tarefa nasce quando ninguém escolhe."""
        colunas = self.listar(projeto_id)
        return colunas[0] if colunas else None
