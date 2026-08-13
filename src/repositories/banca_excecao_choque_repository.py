from datetime import datetime
from typing import List, Optional

from src.models.banca_excecao_choque_model import BancaExcecaoChoqueModel
from src.repositories.base_repository import BaseRepository


class BancaExcecaoChoqueRepository(BaseRepository[BancaExcecaoChoqueModel]):
    model = BancaExcecaoChoqueModel

    def get_pendentes(self) -> List[BancaExcecaoChoqueModel]:
        """A fila da diretoria, do pedido mais antigo para o mais novo.

        Mais antigo primeiro porque quem esperou mais tem a banca mais perto
        de acontecer — decidir por ordem de chegada é o que evita que um pedido
        vença por esquecimento.
        """
        return (
            self.db.query(BancaExcecaoChoqueModel)
            .filter(BancaExcecaoChoqueModel.status == "pendente")
            .order_by(BancaExcecaoChoqueModel.criado_em)
            .all()
        )

    def get_aprovada(
        self, projeto_escopo_id: int, data_hora: datetime
    ) -> Optional[BancaExcecaoChoqueModel]:
        """⭐ A consulta que `_checar_choque` faz: *este* escopo pode marcar
        neste horário?

        ⚠ **O par inteiro, não só o horário.** A exceção antiga era gravada na
        banca que já ocupava a data e, a partir dali, aquele horário virava
        passe livre para qualquer banca — uma liberação pontual abria um buraco
        permanente na regra do §8. Aqui uma aprovação vale para um escopo só.
        """
        return (
            self.db.query(BancaExcecaoChoqueModel)
            .filter(
                BancaExcecaoChoqueModel.projeto_escopo_id == projeto_escopo_id,
                BancaExcecaoChoqueModel.data_hora_pretendida == data_hora,
                BancaExcecaoChoqueModel.status == "aprovada",
            )
            .first()
        )

    def get_pendente_do_par(
        self, projeto_escopo_id: int, data_hora: datetime
    ) -> Optional[BancaExcecaoChoqueModel]:
        """O pedido em aberto para o mesmo par — evita fila com duplicatas
        quando alguém clica duas vezes ou reescreve a justificativa."""
        return (
            self.db.query(BancaExcecaoChoqueModel)
            .filter(
                BancaExcecaoChoqueModel.projeto_escopo_id == projeto_escopo_id,
                BancaExcecaoChoqueModel.data_hora_pretendida == data_hora,
                BancaExcecaoChoqueModel.status == "pendente",
            )
            .first()
        )
