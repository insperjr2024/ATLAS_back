from sqlalchemy.orm import Session
from src.models.avaliacao_model import AvaliacaoModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from src.utils.exceptions import ResourceInUseError


class AvaliacaoRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, banca_id: int, avaliador_id: int, formulario_id: int,
               status: str = "rascunho", comentario_feedback: Optional[str] = None,
               submetida_em: Optional[datetime] = None) -> AvaliacaoModel:
        avaliacao = AvaliacaoModel(
            banca_id=banca_id,
            avaliador_id=avaliador_id,
            formulario_id=formulario_id,
            status=status,
            comentario_feedback=comentario_feedback,
            submetida_em=submetida_em
        )
        self.db.add(avaliacao)
        self.db.commit()
        self.db.refresh(avaliacao)
        return avaliacao

    def get_by_id(self, avaliacao_id: int) -> Optional[AvaliacaoModel]:
        return self.db.query(AvaliacaoModel).filter(AvaliacaoModel.id == avaliacao_id).first()

    def get_all(self) -> List[AvaliacaoModel]:
        return self.db.query(AvaliacaoModel).all()

    def update(self, avaliacao_id: int, **kwargs) -> Optional[AvaliacaoModel]:
        avaliacao = self.get_by_id(avaliacao_id)
        if not avaliacao:
            return None
        for key, value in kwargs.items():
            setattr(avaliacao, key, value)
        self.db.commit()
        self.db.refresh(avaliacao)
        return avaliacao

    def delete(self, avaliacao_id: int) -> bool:
        avaliacao = self.get_by_id(avaliacao_id)
        if not avaliacao:
            return False
        try:
            self.db.delete(avaliacao)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()