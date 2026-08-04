from typing import List, Optional

from src.models.projeto_membro_model import ProjetoMembroModel
from src.repositories.base_repository import BaseRepository


class ProjetoMembroRepository(BaseRepository[ProjetoMembroModel]):
    model = ProjetoMembroModel

    def get_by_projeto(self, projeto_id: int, apenas_atuais: bool = False) -> List[ProjetoMembroModel]:
        query = self.db.query(ProjetoMembroModel).filter(ProjetoMembroModel.projeto_id == projeto_id)
        if apenas_atuais:
            query = query.filter(ProjetoMembroModel.saiu_em.is_(None))
        return query.all()

    def get_atuais_por_usuario(self, usuario_id: int) -> List[ProjetoMembroModel]:
        return (
            self.db.query(ProjetoMembroModel)
            .filter(
                ProjetoMembroModel.usuario_id == usuario_id,
                ProjetoMembroModel.saiu_em.is_(None),
            )
            .all()
        )

    def get_atual_do_usuario_no_projeto(self, projeto_id: int, usuario_id: int) -> Optional[ProjetoMembroModel]:
        return (
            self.db.query(ProjetoMembroModel)
            .filter(
                ProjetoMembroModel.projeto_id == projeto_id,
                ProjetoMembroModel.usuario_id == usuario_id,
                ProjetoMembroModel.saiu_em.is_(None),
            )
            .first()
        )
