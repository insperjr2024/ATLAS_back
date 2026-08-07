from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.configuracao_repository import ConfiguracaoRepository


class UpdateConfiguracaoRequest(BaseModel):
    vagas_por_banca: Optional[int] = None
    lideranca_minima_por_frente: Optional[int] = None


class UpdateConfiguracaoUseCase:
    def __init__(self, db: Session):
        self.repository = ConfiguracaoRepository(db)

    def execute(self, request: UpdateConfiguracaoRequest):
        configuracao = self.repository.get()
        if not configuracao:
            configuracao = self.repository.criar_padrao()
        data = request.dict(exclude_unset=True)
        if data:
            configuracao = self.repository.update(**data)
        return {
            "id": configuracao.id,
            "vagas_por_banca": configuracao.vagas_por_banca,
            "lideranca_minima_por_frente": configuracao.lideranca_minima_por_frente,
        }