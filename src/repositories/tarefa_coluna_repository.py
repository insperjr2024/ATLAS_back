from typing import List

from src.models.tarefa_coluna_model import TarefaColunaModel
from src.repositories.base_repository import BaseRepository


class TarefaColunaRepository(BaseRepository[TarefaColunaModel]):
    model = TarefaColunaModel

    def listar(self) -> List[TarefaColunaModel]:
        return (
            self.db.query(TarefaColunaModel)
            .order_by(TarefaColunaModel.ordem, TarefaColunaModel.id)
            .all()
        )

    def get_por_chave(self, chave: str):
        return self.first_by(chave=chave)

    def proxima_ordem(self) -> int:
        colunas = self.listar()
        return max((c.ordem for c in colunas), default=-1) + 1

    def primeira(self):
        """A coluna onde a tarefa nasce quando ninguém escolhe."""
        colunas = self.listar()
        return colunas[0] if colunas else None
