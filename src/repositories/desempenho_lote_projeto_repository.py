from typing import List

from src.models.desempenho_lote_model import DesempenhoLoteModel
from src.models.desempenho_lote_projeto_model import DesempenhoLoteProjetoModel
from src.repositories.base_repository import BaseRepository
from src.utils.desempenho_lote import esta_aberto


class DesempenhoLoteProjetoRepository(BaseRepository[DesempenhoLoteProjetoModel]):
    model = DesempenhoLoteProjetoModel

    def get_projeto_ids(self, lote_id: int) -> List[int]:
        return [r.projeto_id for r in self.filter_by(lote_id=lote_id)]

    def delete_by_lote(self, lote_id: int) -> None:
        """Usado só quando o lote INTEIRO é apagado (`CancelarBancaUseCase`,
        cancelamento tardio sem ninguém ter respondido nada) — a FK não tem
        cascade, então sem isto o `DELETE` do lote esbarraria nestas linhas."""
        for vinculo in self.filter_by(lote_id=lote_id):
            self.delete(vinculo.id)

    def get_lotes_periodicos_abertos_que_cobrem(self, projeto_id: int) -> List[DesempenhoLoteModel]:
        """Usado na cascata 2.2: lotes periódicos abertos que cobrem `projeto_id`."""
        vinculos = (
            self.db.query(DesempenhoLoteProjetoModel)
            .join(DesempenhoLoteModel, DesempenhoLoteModel.id == DesempenhoLoteProjetoModel.lote_id)
            .filter(DesempenhoLoteProjetoModel.projeto_id == projeto_id, DesempenhoLoteModel.tipo == "periodico")
            .all()
        )
        resultado = []
        for vinculo in vinculos:
            lote = self.db.query(DesempenhoLoteModel).filter(DesempenhoLoteModel.id == vinculo.lote_id).first()
            if lote and esta_aberto(lote.override_manual, lote.data_inicio, lote.data_fim):
                resultado.append(lote)
        return resultado
