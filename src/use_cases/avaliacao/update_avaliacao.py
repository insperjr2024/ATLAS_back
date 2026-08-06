from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.avaliacao_repository import AvaliacaoRepository


class UpdateAvaliacaoRequest(BaseModel):
    banca_id: Optional[int] = None
    formulario_id: Optional[int] = None
    status: Optional[str] = None
    comentario_feedback: Optional[str] = None
    submetida_em: Optional[datetime] = None
    nome_avaliador: Optional[str] = None
    tipo_avaliador: Optional[str] = None
    projeto_avaliado: Optional[str] = None
    escopo_avaliado_id: Optional[int] = None
    escopo_avaliado_outro: Optional[str] = None


class UpdateAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoRepository(db)

    def execute(self, avaliacao_id: int, request: UpdateAvaliacaoRequest):
        data = request.dict(exclude_unset=True)
        avaliacao = self.repository.update(avaliacao_id, **data)
        if not avaliacao:
            return None
        return {
            "id": avaliacao.id,
            "banca_id": avaliacao.banca_id,
            "avaliador_id": avaliacao.avaliador_id,
            "formulario_id": avaliacao.formulario_id,
            "status": avaliacao.status,
            "comentario_feedback": avaliacao.comentario_feedback,
            "submetida_em": avaliacao.submetida_em,
            "nome_avaliador": avaliacao.nome_avaliador,
            "tipo_avaliador": avaliacao.tipo_avaliador,
            "projeto_avaliado": avaliacao.projeto_avaliado,
            "escopo_avaliado_id": avaliacao.escopo_avaliado_id,
            "escopo_avaliado_outro": avaliacao.escopo_avaliado_outro,
        }


class DeleteAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoRepository(db)

    def execute(self, avaliacao_id: int) -> bool:
        return self.repository.delete(avaliacao_id)