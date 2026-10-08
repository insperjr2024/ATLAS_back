from typing import Dict, List, Optional

from src.models.health_track_avaliacao_model import HealthTrackAvaliacaoModel
from src.repositories.base_repository import BaseRepository


class HealthTrackAvaliacaoRepository(BaseRepository[HealthTrackAvaliacaoModel]):
    model = HealthTrackAvaliacaoModel

    def get_historico(self, projeto_id: int, pilar_id: Optional[int] = None) -> List[HealthTrackAvaliacaoModel]:
        """Da mais nova para a mais antiga. `id` desempata as linhas de um
        mesmo preenchimento, que dividem o `avaliado_em`."""
        query = self.db.query(HealthTrackAvaliacaoModel).filter(
            HealthTrackAvaliacaoModel.projeto_id == projeto_id
        )
        if pilar_id is not None:
            query = query.filter(HealthTrackAvaliacaoModel.pilar_id == pilar_id)
        return query.order_by(
            HealthTrackAvaliacaoModel.avaliado_em.desc(), HealthTrackAvaliacaoModel.id.desc()
        ).all()

    def get_ultimas_por_pilar(self, projeto_id: int) -> Dict[int, HealthTrackAvaliacaoModel]:
        """A avaliação mais recente de cada pilar do projeto, por `pilar_id`.

        Varre o histórico do projeto e fica com a primeira de cada pilar. Um
        projeto acumula 6 linhas por ciclo — dezenas, não milhares — e isso
        evita um `GROUP BY` + join de volta que empataria quando dois
        preenchimentos caíssem no mesmo instante.
        """
        ultimas: Dict[int, HealthTrackAvaliacaoModel] = {}
        for avaliacao in self.get_historico(projeto_id):
            ultimas.setdefault(avaliacao.pilar_id, avaliacao)
        return ultimas

    def get_por_projetos(self, projeto_ids: List[int]) -> List[HealthTrackAvaliacaoModel]:
        """O histórico de vários projetos numa consulta, da linha mais nova
        para a mais antiga. É o que o mapa da carteira lê: uma consulta por
        projeto viraria dezenas a cada abertura da página."""
        if not projeto_ids:
            return []
        return (
            self.db.query(HealthTrackAvaliacaoModel)
            .filter(HealthTrackAvaliacaoModel.projeto_id.in_(projeto_ids))
            .order_by(HealthTrackAvaliacaoModel.avaliado_em.desc(), HealthTrackAvaliacaoModel.id.desc())
            .all()
        )

    def registrar_ciclo(self, linhas: List[dict]) -> List[HealthTrackAvaliacaoModel]:
        """Grava as cores de um preenchimento num commit só: ou entram todos
        os pilares, ou nenhum — um ciclo pela metade quebraria a contagem de
        ciclos consecutivos."""
        instancias = [HealthTrackAvaliacaoModel(**linha) for linha in linhas]
        self.db.add_all(instancias)
        self.db.commit()
        for instancia in instancias:
            self.db.refresh(instancia)
        return instancias
