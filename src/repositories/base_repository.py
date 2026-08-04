"""CRUD genérico compartilhado pelos repositórios.

Os 15 repositórios do módulo de bancas repetem o mesmo `get_by_id`/`get_all`/
`update`/`delete` à mão (~50 linhas cada). Os repositórios da Prioridade 1
herdam daqui e ficam com só o que é específico deles.
"""

from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.utils.exceptions import ResourceInUseError

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    model: Type[ModelType]

    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> ModelType:
        instancia = self.model(**kwargs)
        self.db.add(instancia)
        self.db.commit()
        self.db.refresh(instancia)
        return instancia

    def get_by_id(self, registro_id: int) -> Optional[ModelType]:
        return self.db.query(self.model).filter(self.model.id == registro_id).first()

    def get_all(self) -> List[ModelType]:
        return self.db.query(self.model).all()

    def filter_by(self, **kwargs) -> List[ModelType]:
        return self.db.query(self.model).filter_by(**kwargs).all()

    def first_by(self, **kwargs) -> Optional[ModelType]:
        return self.db.query(self.model).filter_by(**kwargs).first()

    def update(self, registro_id: int, **kwargs) -> Optional[ModelType]:
        instancia = self.get_by_id(registro_id)
        if not instancia:
            return None
        for chave, valor in kwargs.items():
            setattr(instancia, chave, valor)
        self.db.commit()
        self.db.refresh(instancia)
        return instancia

    def delete(self, registro_id: int) -> bool:
        instancia = self.get_by_id(registro_id)
        if not instancia:
            return False
        try:
            self.db.delete(instancia)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()

    def bulk_create(self, registros: List[dict]) -> List[ModelType]:
        instancias = [self.model(**r) for r in registros]
        self.db.add_all(instancias)
        self.db.commit()
        return instancias
