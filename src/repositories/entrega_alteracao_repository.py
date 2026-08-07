from typing import List

from src.models.entrega_alteracao_model import EntregaAlteracaoModel
from src.repositories.base_repository import BaseRepository


class EntregaAlteracaoRepository(BaseRepository[EntregaAlteracaoModel]):
    model = EntregaAlteracaoModel

    def get_by_projeto(self, projeto_id: int) -> List[EntregaAlteracaoModel]:
        """As alterações de entrega do projeto, da mais recente para a mais antiga.

        Uma consulta só cobre o projeto e todos os escopos dele: é a aba
        Histórico que consome, e ela monta a linha do tempo do projeto inteiro.
        """
        return (
            self.db.query(EntregaAlteracaoModel)
            .filter(EntregaAlteracaoModel.projeto_id == projeto_id)
            .order_by(EntregaAlteracaoModel.criado_em.desc(), EntregaAlteracaoModel.id.desc())
            .all()
        )
