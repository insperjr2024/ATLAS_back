from datetime import datetime, timedelta
from typing import List

from src.models.desempenho_lote_model import DesempenhoLoteModel
from src.repositories.base_repository import BaseRepository
from src.utils.desempenho_lote import esta_aberto


class DesempenhoLoteRepository(BaseRepository[DesempenhoLoteModel]):
    model = DesempenhoLoteModel

    def get_by_banca_id(self, banca_id: int):
        """O lote que a finalização automática abriu PRA ESTA banca — nulo
        pra toda banca sem lote (banca legada, ou sem escopo vinculado) e
        pra toda banca cuja finalização não rodou ainda. Usado só por
        `CancelarBancaUseCase` pra desfazer o lote certo, e só o certo,
        quando alguém cancela DEPOIS da banca já ter sido realizada."""
        return self.first_by(banca_id=banca_id)

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
