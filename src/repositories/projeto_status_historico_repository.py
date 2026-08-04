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

    def get_ultima(self, projeto_id: int) -> Optional[ProjetoStatusHistoricoModel]:
        return (
            self.db.query(ProjetoStatusHistoricoModel)
            .filter(ProjetoStatusHistoricoModel.projeto_id == projeto_id)
            .order_by(ProjetoStatusHistoricoModel.alterado_em.desc())
            .first()
        )
