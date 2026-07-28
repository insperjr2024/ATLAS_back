from sqlalchemy.orm import Session
from src.models.avaliacao_nota_model import AvaliacaoNotaModel
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from src.utils.exceptions import ResourceInUseError


class AvaliacaoNotaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, avaliacao_id: int, pergunta_id: int,
               nota: Optional[Decimal] = None, resposta_texto: Optional[str] = None) -> AvaliacaoNotaModel:
        avaliacao_nota = AvaliacaoNotaModel(
            avaliacao_id=avaliacao_id,
            pergunta_id=pergunta_id,
            nota=nota,
            resposta_texto=resposta_texto
        )
        self.db.add(avaliacao_nota)
        self.db.commit()
        self.db.refresh(avaliacao_nota)
        return avaliacao_nota

    def get_by_id(self, avaliacao_nota_id: int) -> Optional[AvaliacaoNotaModel]:
        return self.db.query(AvaliacaoNotaModel).filter(AvaliacaoNotaModel.id == avaliacao_nota_id).first()

    def get_all(self) -> List[AvaliacaoNotaModel]:
        return self.db.query(AvaliacaoNotaModel).all()

    def update(self, avaliacao_nota_id: int, **kwargs) -> Optional[AvaliacaoNotaModel]:
        avaliacao_nota = self.get_by_id(avaliacao_nota_id)
        if not avaliacao_nota:
            return None
        for key, value in kwargs.items():
            setattr(avaliacao_nota, key, value)
        self.db.commit()
        self.db.refresh(avaliacao_nota)
        return avaliacao_nota

    def delete(self, avaliacao_nota_id: int) -> bool:
        avaliacao_nota = self.get_by_id(avaliacao_nota_id)
        if not avaliacao_nota:
            return False
        try:
            self.db.delete(avaliacao_nota)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()