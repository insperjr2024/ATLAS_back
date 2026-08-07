from typing import List, Optional

from src.models.cronograma_reajuste_solicitacao_model import CronogramaReajusteSolicitacaoModel
from src.repositories.base_repository import BaseRepository


class CronogramaReajusteRepository(BaseRepository[CronogramaReajusteSolicitacaoModel]):
    model = CronogramaReajusteSolicitacaoModel

    def get_pendente_do_escopo(self, projeto_escopo_id: int) -> Optional[CronogramaReajusteSolicitacaoModel]:
        return self.first_by(projeto_escopo_id=projeto_escopo_id, status="pendente")

    def get_pendentes(self) -> List[CronogramaReajusteSolicitacaoModel]:
        return self.filter_by(status="pendente")

    def get_by_escopo(self, projeto_escopo_id: int) -> List[CronogramaReajusteSolicitacaoModel]:
        """Todos os pedidos daquele escopo — pendentes, aprovados e negados.

        A aba Histórico precisa dos negados também: é a recusa que explica por
        que a janela continuou nos dias vendidos (§8).
        """
        return self.filter_by(projeto_escopo_id=projeto_escopo_id)
