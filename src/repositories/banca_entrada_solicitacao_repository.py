from typing import List, Optional

from src.models.banca_entrada_solicitacao_model import BancaEntradaSolicitacaoModel
from src.repositories.base_repository import BaseRepository


class BancaEntradaSolicitacaoRepository(BaseRepository[BancaEntradaSolicitacaoModel]):
    model = BancaEntradaSolicitacaoModel

    def get_pendentes(self) -> List[BancaEntradaSolicitacaoModel]:
        """A fila da diretoria, do pedido mais antigo para o mais novo — mesma
        ordem dos vizinhos (`BancaForaJanelaRepository.get_pendentes`)."""
        return (
            self.db.query(BancaEntradaSolicitacaoModel)
            .filter(BancaEntradaSolicitacaoModel.status == "pendente")
            .order_by(BancaEntradaSolicitacaoModel.criado_em)
            .all()
        )

    def get_pendente_do_par(
        self, banca_id: int, usuario_id: int
    ) -> Optional[BancaEntradaSolicitacaoModel]:
        """O pedido em aberto desta pessoa para esta banca — pedir de novo
        reescreve a justificativa, não enfileira duplicata."""
        return (
            self.db.query(BancaEntradaSolicitacaoModel)
            .filter(
                BancaEntradaSolicitacaoModel.banca_id == banca_id,
                BancaEntradaSolicitacaoModel.usuario_id == usuario_id,
                BancaEntradaSolicitacaoModel.status == "pendente",
            )
            .first()
        )
