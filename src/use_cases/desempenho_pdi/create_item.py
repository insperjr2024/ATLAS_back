from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository
from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.utils.exceptions import RegraDeNegocioError


class CreatePdiItemRequest(BaseModel):
    nome: str
    tipo_arquivo: str = "qualquer"  # "documento" | "foto" | "qualquer"


def serializar_item(item) -> dict:
    return {
        "id": item.id,
        "pasta_id": item.pasta_id,
        "nome": item.nome,
        "tipo_arquivo": item.tipo_arquivo,
        "ordem": item.ordem,
    }


class CreatePdiItemUseCase:
    """Um documento exigido dentro da pasta (ex: "Foto", "Relatório") — a
    checklist que o mentorado precisa completar. `ordem` entra automática,
    sempre depois do último item da mesma pasta."""

    def __init__(self, db: Session):
        self.repository = DesempenhoPdiItemRepository(db)
        self.pasta_repository = DesempenhoPdiPastaRepository(db)

    def execute(self, pasta_id: int, request: CreatePdiItemRequest) -> dict:
        if not self.pasta_repository.get_by_id(pasta_id):
            raise RegraDeNegocioError("Pasta de PDI não encontrada")
        item = self.repository.create(
            pasta_id=pasta_id,
            nome=request.nome,
            tipo_arquivo=request.tipo_arquivo,
            ordem=self.repository.get_proxima_ordem(pasta_id),
        )
        return serializar_item(item)
