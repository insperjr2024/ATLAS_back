"""A evolução da carteira (Health Track §16): um ponto por rodada concluída,
mais "hoje".

Cada ponto é uma foto da carteira NAQUELE momento: pra cada projeto da
rodada, a cor vigente de cada pilar até a conclusão da rodada, e o status
geral pela regra ATUAL (réguas iguais em todos os pontos, senão a curva
mudaria só porque a diretoria mexeu na regra). Só projeto com todos os
pilares ativos coloridos conta no status; no gráfico por pilar conta
qualquer cor que exista.

"Hoje" é a mesma foto sobre quem está em acompanhamento agora, pra curva
não parar na última rodada.
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from src.models.projeto_model import ProjetoModel
from src.repositories.health_track_avaliacao_repository import HealthTrackAvaliacaoRepository
from src.repositories.health_track_pilar_repository import HealthTrackPilarRepository
from src.repositories.health_track_regra_repository import HealthTrackRegraRepository
from src.repositories.health_track_rodada_repository import (
    HealthTrackRodadaProjetoRepository,
    HealthTrackRodadaRepository,
)
from src.use_cases.health_track.rodadas import EM_ACOMPANHAMENTO
from src.use_cases.health_track.serializar import serializar_pilar
from src.utils.fuso import agora_utc
from src.utils.health_track_status import ReguasStatus, calcular_status_geral


class GetEvolucaoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.pilar_repo = HealthTrackPilarRepository(db)
        self.avaliacao_repo = HealthTrackAvaliacaoRepository(db)
        self.regra_repo = HealthTrackRegraRepository(db)
        self.rodada_repo = HealthTrackRodadaRepository(db)
        self.item_repo = HealthTrackRodadaProjetoRepository(db)

    def execute(self) -> dict:
        pilares = self.pilar_repo.get_ativos()
        ids_pilares = [p.id for p in pilares]
        regra = ReguasStatus(self.regra_repo.get_versoes()).atual()

        rodadas = [r for r in self.rodada_repo.get_todas() if r.concluida_em is not None]
        rodadas.sort(key=lambda r: r.concluida_em)
        itens = self.item_repo.get_by_rodadas([r.id for r in rodadas])
        projetos_da_rodada: Dict[int, List[int]] = defaultdict(list)
        for i in itens:
            projetos_da_rodada[i.rodada_id].append(i.projeto_id)

        em_acompanhamento = [
            p.id
            for p in self.db.query(ProjetoModel.id)
            .filter(ProjetoModel.arquivado_em.is_(None))
            .filter(ProjetoModel.institucional.is_(False))
            .filter(ProjetoModel.status.in_(EM_ACOMPANHAMENTO))
        ]

        todos = set(em_acompanhamento) | {pid for ids in projetos_da_rodada.values() for pid in ids}
        historico: Dict[int, list] = defaultdict(list)
        for a in self.avaliacao_repo.get_por_projetos(sorted(todos)):
            historico[a.projeto_id].append(a)

        pontos = [
            foto(f"Rodada {n}", r.concluida_em, projetos_da_rodada.get(r.id, []), historico, ids_pilares, regra)
            for n, r in enumerate(rodadas, start=1)
        ]
        pontos.append(foto("Hoje", agora_utc(), em_acompanhamento, historico, ids_pilares, regra))
        return {"pilares": [serializar_pilar(p) for p in pilares], "pontos": pontos}


def foto(
    rotulo: str,
    em: datetime,
    projetos: Iterable[int],
    historico: Dict[int, list],
    ids_pilares: List[int],
    regra,
) -> dict:
    """A carteira em `em`: cor vigente de cada pilar de cada projeto até ali."""
    por_cor = {"verde": 0, "amarelo": 0, "vermelho": 0}
    por_pilar = {str(pid): {"verde": 0, "amarelo": 0, "vermelho": 0} for pid in ids_pilares}
    avaliados = 0
    total = 0
    for pid in projetos:
        total += 1
        ultimas: Dict[int, Optional[str]] = {}
        for a in historico.get(pid, []):
            if a.avaliado_em <= em:
                ultimas.setdefault(a.pilar_id, a.cor)
        cores = [ultimas.get(p) for p in ids_pilares]
        for p, cor in zip(ids_pilares, cores):
            if cor:
                por_pilar[str(p)][cor] += 1
        if regra and all(cores):
            avaliados += 1
            por_cor[calcular_status_geral(cores, regra)] += 1
    return {
        "rotulo": rotulo,
        "em": em,
        "total": total,
        "avaliados": avaliados,
        **por_cor,
        "pilares": por_pilar,
    }
