from typing import List

from sqlalchemy.orm import Session, defer

from src.models.ex_membro_model import ExMembroModel
from src.repositories.base_repository import BaseRepository


class ExMembroRepository(BaseRepository[ExMembroModel]):
    model = ExMembroModel

    def __init__(self, db: Session):
        super().__init__(db)

    def _ordenados(self):
        # `defer(foto)`: a listagem nunca precisa dos bytes da foto (ela sai
        # por rota própria). Sem isto cada GET da lista carregaria ~1 MB.
        return (
            self.db.query(ExMembroModel)
            .options(defer(ExMembroModel.foto))
            .order_by(ExMembroModel.ordem.asc(), ExMembroModel.id.asc())
        )

    def listar_todos(self) -> List[ExMembroModel]:
        return self._ordenados().all()

    def listar_publicados(self) -> List[ExMembroModel]:
        return self._ordenados().filter(ExMembroModel.publicado.is_(True)).all()

    def proxima_ordem(self) -> int:
        maior = self.db.query(ExMembroModel.ordem).order_by(ExMembroModel.ordem.desc()).first()
        return (maior[0] + 1) if maior else 0

    def existe_nome(self, nome: str) -> bool:
        return self.db.query(ExMembroModel.id).filter(ExMembroModel.nome == nome).first() is not None
