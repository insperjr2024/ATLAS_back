from sqlalchemy.orm import Session
from src.models.pergunta_model import PerguntaModel
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from src.utils.exceptions import ResourceInUseError


class PerguntaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, formulario_id: int, texto: str, ordem: int,
               tipo_resposta: str = "nota") -> PerguntaModel:
        pergunta = PerguntaModel(
            formulario_id=formulario_id,
            texto=texto,
            ordem=ordem,
            tipo_resposta=tipo_resposta
        )
        self.db.add(pergunta)
        self.db.commit()
        self.db.refresh(pergunta)
        return pergunta

    def get_by_id(self, pergunta_id: int) -> Optional[PerguntaModel]:
        return self.db.query(PerguntaModel).filter(PerguntaModel.id == pergunta_id).first()

    def get_all(self) -> List[PerguntaModel]:
        return self.db.query(PerguntaModel).all()

    def update(self, pergunta_id: int, **kwargs) -> Optional[PerguntaModel]:
        pergunta = self.get_by_id(pergunta_id)
        if not pergunta:
            return None
        for key, value in kwargs.items():
            setattr(pergunta, key, value)
        self.db.commit()
        self.db.refresh(pergunta)
        return pergunta

    def delete(self, pergunta_id: int) -> bool:
        pergunta = self.get_by_id(pergunta_id)
        if not pergunta:
            return False
        try:
            self.db.delete(pergunta)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()