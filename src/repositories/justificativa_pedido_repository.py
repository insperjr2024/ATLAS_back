from typing import List, Optional

from src.models.justificativa_pedido_model import JustificativaPedidoModel
from src.repositories.base_repository import BaseRepository


class JustificativaPedidoRepository(BaseRepository[JustificativaPedidoModel]):
    model = JustificativaPedidoModel

    def get_abertos_por_projetos(self, projeto_ids: List[int]) -> List[JustificativaPedidoModel]:
        """Os pedidos que ainda esperam resposta, em lote.

        Em lote porque a fila de Aprovações precisa de todos de uma vez para
        decidir, por linha, entre mostrar o botão de pedir e o selo de
        "aguardando o coordenador".
        """
        if not projeto_ids:
            return []
        return (
            self.db.query(self.model)
            .filter(
                self.model.projeto_id.in_(projeto_ids),
                self.model.respondido_em.is_(None),
            )
            .all()
        )

    def get_aberto_do_motivo(
        self, projeto_id: int, projeto_escopo_id: Optional[int], tipo: Optional[str]
    ) -> Optional[JustificativaPedidoModel]:
        """O pedido aberto para ESTE motivo — a chave da deduplicação.

        Sem isto, clicar duas vezes em "Pedir explicação" gera dois pedidos e
        duas notificações para a mesma pergunta.
        """
        return (
            self.db.query(self.model)
            .filter(
                self.model.projeto_id == projeto_id,
                self.model.projeto_escopo_id.is_(None)
                if projeto_escopo_id is None
                else self.model.projeto_escopo_id == projeto_escopo_id,
                self.model.tipo.is_(None) if tipo is None else self.model.tipo == tipo,
                self.model.respondido_em.is_(None),
            )
            .first()
        )

    def get_abertos_do_projeto(self, projeto_id: int) -> List[JustificativaPedidoModel]:
        return (
            self.db.query(self.model)
            .filter(self.model.projeto_id == projeto_id, self.model.respondido_em.is_(None))
            .all()
        )
