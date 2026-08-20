from datetime import datetime
from typing import List, Optional

from src.models.banca_fora_janela_solicitacao_model import BancaForaJanelaSolicitacaoModel
from src.repositories.base_repository import BaseRepository


class BancaForaJanelaRepository(BaseRepository[BancaForaJanelaSolicitacaoModel]):
    model = BancaForaJanelaSolicitacaoModel

    def get_pendentes(self) -> List[BancaForaJanelaSolicitacaoModel]:
        """A fila da diretoria, do pedido mais antigo para o mais novo — mesma
        ordem de `BancaExcecaoChoqueRepository.get_pendentes`."""
        return (
            self.db.query(BancaForaJanelaSolicitacaoModel)
            .filter(BancaForaJanelaSolicitacaoModel.status == "pendente")
            .order_by(BancaForaJanelaSolicitacaoModel.criado_em)
            .all()
        )

    def get_aprovada(
        self, projeto_escopo_id: int, data_hora: datetime
    ) -> Optional[BancaForaJanelaSolicitacaoModel]:
        """A consulta que `_exigir_janela` faz: este escopo pode marcar
        banca nesta data, mesmo fora da janela?"""
        return (
            self.db.query(BancaForaJanelaSolicitacaoModel)
            .filter(
                BancaForaJanelaSolicitacaoModel.projeto_escopo_id == projeto_escopo_id,
                BancaForaJanelaSolicitacaoModel.data_hora_pretendida == data_hora,
                BancaForaJanelaSolicitacaoModel.status == "aprovada",
            )
            .first()
        )

    def get_pendente_do_par(
        self, projeto_escopo_id: int, data_hora: datetime
    ) -> Optional[BancaForaJanelaSolicitacaoModel]:
        """O pedido em aberto para o mesmo par — pedir de novo reescreve,
        não enfileira duplicata."""
        return (
            self.db.query(BancaForaJanelaSolicitacaoModel)
            .filter(
                BancaForaJanelaSolicitacaoModel.projeto_escopo_id == projeto_escopo_id,
                BancaForaJanelaSolicitacaoModel.data_hora_pretendida == data_hora,
                BancaForaJanelaSolicitacaoModel.status == "pendente",
            )
            .first()
        )
