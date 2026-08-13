from typing import Dict, Iterable, List, Optional

from src.models.banca_sessao_model import BancaSessaoModel
from src.repositories.base_repository import BaseRepository


class BancaSessaoRepository(BaseRepository[BancaSessaoModel]):
    model = BancaSessaoModel

    def get_by_banca(self, banca_id: int) -> List[BancaSessaoModel]:
        """As sessões da banca, da primeira para a última."""
        return (
            self.db.query(BancaSessaoModel)
            .filter(BancaSessaoModel.banca_id == banca_id)
            .order_by(BancaSessaoModel.numero)
            .all()
        )

    def get_by_bancas(self, banca_ids: Iterable[int]) -> Dict[int, List[BancaSessaoModel]]:
        """`{banca_id: [sessões]}` — para telas que listam várias bancas.

        Existe para o histórico do projeto e a lista de bancas não fazerem uma
        consulta por linha.
        """
        ids = list(banca_ids)
        if not ids:
            return {}
        agrupado: Dict[int, List[BancaSessaoModel]] = {}
        linhas = (
            self.db.query(BancaSessaoModel)
            .filter(BancaSessaoModel.banca_id.in_(ids))
            .order_by(BancaSessaoModel.banca_id, BancaSessaoModel.numero)
            .all()
        )
        for sessao in linhas:
            agrupado.setdefault(sessao.banca_id, []).append(sessao)
        return agrupado

    def get_corrente(self, banca_id: int) -> Optional[BancaSessaoModel]:
        """A sessão em aberto — a que espelha o estado atual de `banca`.

        ⚠ `encerrada_em is None` é a régua, não o maior `numero`: uma banca
        aprovada tem a última sessão encerrada e nenhuma corrente, e é isso que
        distingue "acabou" de "está rolando outra".
        """
        return (
            self.db.query(BancaSessaoModel)
            .filter(
                BancaSessaoModel.banca_id == banca_id,
                BancaSessaoModel.encerrada_em.is_(None),
            )
            .order_by(BancaSessaoModel.numero.desc())
            .first()
        )

    def proximo_numero(self, banca_id: int) -> int:
        """Quantas sessões esta banca já teve, +1."""
        return (
            self.db.query(BancaSessaoModel)
            .filter(BancaSessaoModel.banca_id == banca_id)
            .count()
            + 1
        )
