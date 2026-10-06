from typing import List, Optional

from src.models.desempenho_avaliacao_model import DesempenhoAvaliacaoModel
from src.repositories.base_repository import BaseRepository


class DesempenhoAvaliacaoRepository(BaseRepository[DesempenhoAvaliacaoModel]):
    model = DesempenhoAvaliacaoModel

    def get_by_lote(self, lote_id: int) -> List[DesempenhoAvaliacaoModel]:
        return self.filter_by(lote_id=lote_id)

    def get_recebidas_por(self, avaliado_id: int) -> List[DesempenhoAvaliacaoModel]:
        return self.filter_by(avaliado_id=avaliado_id)

    def existe_par(self, lote_id: int, avaliador_id: int, avaliado_id: int) -> bool:
        """A avaliação entre pessoas (sem escopo) já foi respondida?"""
        return (
            self.first_by(
                lote_id=lote_id,
                avaliador_id=avaliador_id,
                avaliado_id=avaliado_id,
                projeto_escopo_id=None,
            )
            is not None
        )

    def respondeu_escopo(self, lote_id: int, usuario_id: int, projeto_escopo_id: int) -> bool:
        """A Avaliação do Escopo de `projeto_escopo_id` já foi respondida por
        `usuario_id` neste lote? Uma resposta antiga (de antes de 2026-10-05,
        sem escopo) conta como respondida pra todos os escopos do lote: era
        uma só por pessoa, e não faz sentido cobrar de novo."""
        return (
            self.first_by(
                lote_id=lote_id,
                avaliador_id=usuario_id,
                avaliado_id=usuario_id,
                projeto_escopo_id=projeto_escopo_id,
            )
            is not None
            or self.existe_par(lote_id, usuario_id, usuario_id)
        )

    def get_par(self, lote_id: int, avaliador_id: int, avaliado_id: int) -> Optional[DesempenhoAvaliacaoModel]:
        return self.first_by(lote_id=lote_id, avaliador_id=avaliador_id, avaliado_id=avaliado_id)
