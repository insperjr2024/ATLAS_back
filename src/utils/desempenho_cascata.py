from typing import List

from sqlalchemy.orm import Session

from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.utils.desempenho_lote import esta_aberto


def aplicar_cascata_finalizacao(db: Session, projeto_ids: List[int]) -> None:
    """Regra 2.2: ao criar um lote de finalização cobrindo `projeto_ids`,
    remove esses projetos de qualquer lote periódico ABERTO que também os
    cobrisse — a mesma pessoa não deve receber periódica e finalização do
    mesmo projeto ao mesmo tempo."""
    lote_repo = DesempenhoLoteRepository(db)
    lote_projeto_repo = DesempenhoLoteProjetoRepository(db)

    lotes_periodicos = [
        lote
        for lote in lote_repo.filter_by(tipo="periodico")
        if esta_aberto(lote.override_manual, lote.data_inicio, lote.data_fim)
    ]
    projeto_ids_set = set(projeto_ids)
    for lote in lotes_periodicos:
        cobertos = set(lote_projeto_repo.get_projeto_ids(lote.id))
        for projeto_id in projeto_ids_set & cobertos:
            vinculo = lote_projeto_repo.first_by(lote_id=lote.id, projeto_id=projeto_id)
            if vinculo:
                lote_projeto_repo.delete(vinculo.id)
