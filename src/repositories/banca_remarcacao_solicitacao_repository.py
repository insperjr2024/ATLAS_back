from typing import List, Optional

from src.models.banca_remarcacao_solicitacao_model import BancaRemarcacaoSolicitacaoModel
from src.repositories.base_repository import BaseRepository


class BancaRemarcacaoSolicitacaoRepository(BaseRepository[BancaRemarcacaoSolicitacaoModel]):
    model = BancaRemarcacaoSolicitacaoModel

    def get_pendentes(self) -> List[BancaRemarcacaoSolicitacaoModel]:
        """A fila da diretoria, do pedido mais antigo para o mais novo — mesma
        ordem de `BancaForaJanelaRepository.get_pendentes`."""
        return (
            self.db.query(BancaRemarcacaoSolicitacaoModel)
            .filter(BancaRemarcacaoSolicitacaoModel.status == "pendente")
            .order_by(BancaRemarcacaoSolicitacaoModel.criado_em)
            .all()
        )

    def get_pendente_da_banca(
        self, banca_id: int
    ) -> Optional[BancaRemarcacaoSolicitacaoModel]:
        """O pedido em aberto para esta banca — pedir de novo (outra data, outro
        texto) REESCREVE o pendente em vez de enfileirar um segundo. Só cabe uma
        remarcação por vez em análise; é uma data nova, não várias."""
        return (
            self.db.query(BancaRemarcacaoSolicitacaoModel)
            .filter(
                BancaRemarcacaoSolicitacaoModel.banca_id == banca_id,
                BancaRemarcacaoSolicitacaoModel.status == "pendente",
            )
            .first()
        )
