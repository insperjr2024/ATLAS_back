from typing import Optional

from sqlalchemy.orm import Session

from src.models.identidade_institucional_model import IdentidadeInstitucionalModel


class IdentidadeInstitucionalRepository:
    """Linha única (id=1) — a migration já semeia com os valores vigentes,
    então `get()` nunca deveria voltar `None` em uso normal."""

    def __init__(self, db: Session):
        self.db = db

    def get(self) -> Optional[IdentidadeInstitucionalModel]:
        return self.db.query(IdentidadeInstitucionalModel).first()

    def update(self, **kwargs) -> Optional[IdentidadeInstitucionalModel]:
        identidade = self.get()
        if not identidade:
            return None
        for key, value in kwargs.items():
            setattr(identidade, key, value)
        self.db.commit()
        self.db.refresh(identidade)
        return identidade
