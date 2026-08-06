from datetime import date
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.repositories.semestre_repository import SemestreRepository
from src.use_cases.desempenho_pdi.create_pasta import serializar_pasta


class UpdatePdiPastaRequest(BaseModel):
    nome: Optional[str] = None
    prazo: Optional[date] = None
    ordem: Optional[int] = None


class UpdatePdiPastaUseCase:
    """`tipo` não entra aqui de propósito: trocar "inicial" por "encontro"
    depois de já existirem envios mudaria quem tinha permissão de enviar sem
    aviso nenhum — se a diretoria errou o tipo, o caminho é excluir (só
    funciona sem envio, ver `DeletePdiPastaUseCase`) e criar de novo."""

    def __init__(self, db: Session):
        self.repository = DesempenhoPdiPastaRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, pasta_id: int, request: UpdatePdiPastaRequest) -> Optional[dict]:
        dados = request.model_dump(exclude_unset=True)
        pasta = self.repository.update(pasta_id, **dados)
        if not pasta:
            return None
        return serializar_pasta(pasta, self.semestre_repository)
