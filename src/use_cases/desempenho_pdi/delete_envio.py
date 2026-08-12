from sqlalchemy.orm import Session

from src.repositories.desempenho_pdi_envio_repository import DesempenhoPdiEnvioRepository
from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository
from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.use_cases.desempenho_pdi.upload_envio import pode_enviar_pdi
from src.utils.exceptions import RegraDeNegocioError


class DeletePdiEnvioUseCase:
    """Mesma permissão de quem pode enviar — quem pode subir um arquivo
    também pode tirar, pra corrigir um envio errado."""

    def __init__(self, db: Session):
        self.db = db
        self.item_repository = DesempenhoPdiItemRepository(db)
        self.pasta_repository = DesempenhoPdiPastaRepository(db)
        self.envio_repository = DesempenhoPdiEnvioRepository(db)

    def execute(self, item_id: int, mentorado_id: int, current_user) -> bool:
        item = self.item_repository.get_by_id(item_id)
        if not item:
            raise RegraDeNegocioError("Item de PDI não encontrado")
        pasta = self.pasta_repository.get_by_id(item.pasta_id)
        if not pasta:
            raise RegraDeNegocioError("Pasta de PDI não encontrada")
        if not pode_enviar_pdi(pasta, mentorado_id, current_user, self.db):
            raise RegraDeNegocioError("Você não tem permissão para remover este envio")

        envio = self.envio_repository.get_por_item_e_mentorado(item_id, mentorado_id)
        if not envio:
            return False
        return self.envio_repository.delete(envio.id)
