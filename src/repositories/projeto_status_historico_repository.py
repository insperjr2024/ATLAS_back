from typing import List, Optional

from src.models.projeto_status_historico_model import ProjetoStatusHistoricoModel
from src.repositories.base_repository import BaseRepository


class ProjetoStatusHistoricoRepository(BaseRepository[ProjetoStatusHistoricoModel]):
    model = ProjetoStatusHistoricoModel

    def get_by_projeto(self, projeto_id: int) -> List[ProjetoStatusHistoricoModel]:
        return (
            self.db.query(ProjetoStatusHistoricoModel)
            .filter(ProjetoStatusHistoricoModel.projeto_id == projeto_id)
            .order_by(ProjetoStatusHistoricoModel.alterado_em)
            .all()
        )

    def get_by_projetos(self, projeto_ids: List[int]) -> List[ProjetoStatusHistoricoModel]:
        """O mesmo, para vários projetos — o Monitoramento varre o portfólio.

        O histórico é o que revela as janelas de ⏸ Pausado, e elas entram na
        conta de atraso (`contagem_dias.calcular_contagem_projeto`). Chamar
        `get_by_projeto` dentro do laço seria uma query por projeto.
        """
        if not projeto_ids:
            return []
        return (
            self.db.query(ProjetoStatusHistoricoModel)
            .filter(ProjetoStatusHistoricoModel.projeto_id.in_(projeto_ids))
            .order_by(ProjetoStatusHistoricoModel.alterado_em)
            .all()
        )

    def get_ultima(self, projeto_id: int) -> Optional[ProjetoStatusHistoricoModel]:
        return (
            self.db.query(ProjetoStatusHistoricoModel)
            .filter(ProjetoStatusHistoricoModel.projeto_id == projeto_id)
            .order_by(ProjetoStatusHistoricoModel.alterado_em.desc())
            .first()
        )
