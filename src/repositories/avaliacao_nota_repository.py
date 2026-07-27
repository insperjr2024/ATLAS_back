from sqlalchemy.orm import Session
from src.models.avaliacao_nota_model import AvaliacaoNotaModel
from typing import List, Optional
from decimal import Decimal


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