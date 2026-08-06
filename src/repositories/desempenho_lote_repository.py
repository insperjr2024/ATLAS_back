from datetime import datetime, timedelta
from typing import List

from src.models.desempenho_lote_model import DesempenhoLoteModel
from src.repositories.base_repository import BaseRepository
from src.utils.desempenho_lote import esta_aberto


class DesempenhoLoteRepository(BaseRepository[DesempenhoLoteModel]):
    model = DesempenhoLoteModel

    def get_abertos_agora(self) -> List[DesempenhoLoteModel]:
        return [
            lote
            for lote in self.get_all()
            if esta_aberto(lote.override_manual, lote.data_inicio, lote.data_fim)
        ]

    def get_relevantes_para_fila(self, dias_janela: int = 30) -> List[DesempenhoLoteModel]:
        """Abertos + fechados recentemente (regra: quem tinha pendência e o
        lote fechou — manualmente ou pelo prazo — ainda merece aparecer na
        fila, marcado como fechado, por um tempo. Sem isso a pendência só
        some sem aviso nenhum. Passado o prazo é uma rodada velha, deixa de
        poluir a fila de quem nunca respondeu."""
        limite = datetime.now() - timedelta(days=dias_janela)
        return [
            lote
            for lote in self.get_all()
            if esta_aberto(lote.override_manual, lote.data_inicio, lote.data_fim)
            or lote.data_fim >= limite
        ]
