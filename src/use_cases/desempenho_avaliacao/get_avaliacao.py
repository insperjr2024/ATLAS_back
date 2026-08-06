from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.desempenho_avaliacao_nota_repository import DesempenhoAvaliacaoNotaRepository
from src.repositories.desempenho_avaliacao_repository import DesempenhoAvaliacaoRepository
from src.repositories.desempenho_criterio_repository import DesempenhoCriterioRepository


def serializar_avaliacao_resumo(a) -> dict:
    return {
        "id": a.id,
        "lote_id": a.lote_id,
        "formulario_id": a.formulario_id,
        "avaliador_id": a.avaliador_id,
        "avaliado_id": a.avaliado_id,
        "nota_geral": a.nota_geral,
        "comentarios": a.comentarios,
        "criado_em": a.criado_em,
    }


class ListDesempenhoAvaliacoesUseCase:
    def __init__(self, db: Session):
        self.repository = DesempenhoAvaliacaoRepository(db)

    def execute(self) -> list[dict]:
        return [serializar_avaliacao_resumo(a) for a in self.repository.get_all()]


class GetDesempenhoAvaliacaoUseCase:
    """Detalhe completo de uma avaliação — quem respondeu, quando, e a nota
    (ou resposta em texto) de cada critério, com o rótulo já resolvido."""

    def __init__(self, db: Session):
        self.avaliacao_repo = DesempenhoAvaliacaoRepository(db)
        self.avaliacao_nota_repo = DesempenhoAvaliacaoNotaRepository(db)
        self.criterio_repo = DesempenhoCriterioRepository(db)

    def execute(self, avaliacao_id: int) -> Optional[dict]:
        avaliacao = self.avaliacao_repo.get_by_id(avaliacao_id)
        if not avaliacao:
            return None

        notas = self.avaliacao_nota_repo.get_by_avaliacao(avaliacao_id)
        notas_resp = []
        for n in notas:
            criterio = self.criterio_repo.get_by_id(n.criterio_id)
            notas_resp.append(
                {
                    "criterio_id": n.criterio_id,
                    "label": criterio.label if criterio else None,
                    "tipo_resposta": criterio.tipo_resposta if criterio else None,
                    "nota": n.nota,
                    "resposta_texto": n.resposta_texto,
                }
            )

        return {**serializar_avaliacao_resumo(avaliacao), "notas": notas_resp}
