from typing import Iterable, List

from src.models.banca_remarcacao_model import BancaRemarcacaoModel
from src.repositories.base_repository import BaseRepository


class BancaRemarcacaoRepository(BaseRepository[BancaRemarcacaoModel]):
    model = BancaRemarcacaoModel

    def get_by_banca(self, banca_id: int) -> List[BancaRemarcacaoModel]:
        """As remarcações de uma banca, da mais recente para a mais antiga."""
        return (
            self.db.query(BancaRemarcacaoModel)
            .filter(BancaRemarcacaoModel.banca_id == banca_id)
            .order_by(BancaRemarcacaoModel.criado_em.desc(), BancaRemarcacaoModel.id.desc())
            .all()
        )

    def get_by_bancas(self, banca_ids: Iterable[int]) -> List[BancaRemarcacaoModel]:
        """Todas as remarcações de um conjunto de bancas, numa consulta só.

        É o que a aba Histórico precisa: ela monta a linha do tempo do PROJETO,
        que pode ter várias bancas, e pedir uma por uma seria N consultas para
        desenhar uma tela de leitura.
        """
        ids = list(banca_ids)
        if not ids:
            return []
        return (
            self.db.query(BancaRemarcacaoModel)
            .filter(BancaRemarcacaoModel.banca_id.in_(ids))
            .order_by(BancaRemarcacaoModel.criado_em.desc(), BancaRemarcacaoModel.id.desc())
            .all()
        )
