from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository


class UpdateDescricaoRequest(BaseModel):
    descricao: Optional[str] = None


class UpdateDescricaoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: UpdateDescricaoRequest):
        projeto = self.repository.update(projeto_id, descricao=request.descricao)
        if not projeto:
            return None
        return {"id": projeto.id, "descricao": projeto.descricao}
