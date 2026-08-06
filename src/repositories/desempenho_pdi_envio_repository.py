from typing import List, Optional

from src.models.desempenho_pdi_envio_model import DesempenhoPdiEnvioModel
from src.models.desempenho_pdi_item_model import DesempenhoPdiItemModel
from src.repositories.base_repository import BaseRepository


class DesempenhoPdiEnvioRepository(BaseRepository[DesempenhoPdiEnvioModel]):
    model = DesempenhoPdiEnvioModel

    def get_por_item_e_mentorado(self, item_id: int, mentorado_id: int) -> Optional[DesempenhoPdiEnvioModel]:
        return self.first_by(item_id=item_id, mentorado_id=mentorado_id)

    def get_por_mentorado(self, mentorado_id: int) -> List[DesempenhoPdiEnvioModel]:
        return self.filter_by(mentorado_id=mentorado_id)

    def get_por_item(self, item_id: int) -> List[DesempenhoPdiEnvioModel]:
        return self.filter_by(item_id=item_id)

    def get_por_pasta(self, pasta_id: int) -> List[DesempenhoPdiEnvioModel]:
        """O envio não tem mais `pasta_id` direto (ver `DesempenhoPdiEnvioModel`)
        — passa pelo item pra achar todos os envios de uma pasta inteira.
        Usado pelo cron (`rodar_lembrete_prazo_pdi`), que decide por pasta."""
        return (
            self.db.query(self.model)
            .join(DesempenhoPdiItemModel, DesempenhoPdiItemModel.id == self.model.item_id)
            .filter(DesempenhoPdiItemModel.pasta_id == pasta_id)
            .all()
        )
