from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from src.repositories.configuracao_repository import ConfiguracaoRepository


class UpdateConfiguracaoRequest(BaseModel):
    vagas_por_banca: Optional[int] = None
    lideranca_minima_por_frente: Optional[int] = None
    health_track_persistencia_amarelo: Optional[int] = Field(default=None, ge=1, le=20)
    health_track_persistencia_vermelho: Optional[int] = Field(default=None, ge=1, le=20)


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
            "health_track_persistencia_amarelo": configuracao.health_track_persistencia_amarelo,
            "health_track_persistencia_vermelho": configuracao.health_track_persistencia_vermelho,
        }