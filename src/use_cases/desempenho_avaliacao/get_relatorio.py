from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.desempenho_avaliacao_nota_repository import DesempenhoAvaliacaoNotaRepository
from src.repositories.desempenho_avaliacao_repository import DesempenhoAvaliacaoRepository
from src.repositories.desempenho_criterio_repository import DesempenhoCriterioRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository


class GetRelatorioDesempenhoUseCase:
    """Agrega as avaliações RECEBIDAS por `usuario_id`, por lote: média da
    nota geral, média (ou respostas de texto) por critério, e a lista de
    comentários. A cor por nota (regra 2.9, `< 3` = atenção) fica pro front —
    aqui só vão os números."""

    def __init__(self, db: Session):
        self.avaliacao_repo = DesempenhoAvaliacaoRepository(db)
        self.avaliacao_nota_repo = DesempenhoAvaliacaoNotaRepository(db)
        self.criterio_repo = DesempenhoCriterioRepository(db)
        self.lote_repo = DesempenhoLoteRepository(db)

    def execute(self, usuario_id: int, lote_id: Optional[int] = None, tipo: Optional[str] = None) -> dict:
        avaliacoes = self.avaliacao_repo.get_recebidas_por(usuario_id)

        lotes_por_id = {lote.id: lote for lote in self.lote_repo.get_all()}
        if lote_id is not None:
            avaliacoes = [a for a in avaliacoes if a.lote_id == lote_id]
        if tipo is not None:
            avaliacoes = [a for a in avaliacoes if lotes_por_id.get(a.lote_id) and lotes_por_id[a.lote_id].tipo == tipo]

        agrupado_por_lote: dict[int, list] = {}
        for avaliacao in avaliacoes:
            agrupado_por_lote.setdefault(avaliacao.lote_id, []).append(avaliacao)

        criterios_cache: dict[int, object] = {}

        def get_criterio(criterio_id: int):
            if criterio_id not in criterios_cache:
                criterios_cache[criterio_id] = self.criterio_repo.get_by_id(criterio_id)
            return criterios_cache[criterio_id]

        lotes_resp = []
        for lid, avals in agrupado_por_lote.items():
            lote = lotes_por_id.get(lid)
            notas_geral = [a.nota_geral for a in avals]
            comentarios = [a.comentarios for a in avals if a.comentarios]

            todas_notas = self.avaliacao_nota_repo.get_by_avaliacoes([a.id for a in avals])
            por_criterio: dict[int, list] = {}
            for n in todas_notas:
                por_criterio.setdefault(n.criterio_id, []).append(n)

            criterios_resp = []
            for criterio_id, notas in por_criterio.items():
                criterio = get_criterio(criterio_id)
                if not criterio:
                    continue
                if criterio.tipo_resposta == "nota":
                    valores = [n.nota for n in notas if n.nota is not None]
                    criterios_resp.append(
                        {
                            "criterio_id": criterio_id,
                            "label": criterio.label,
                            "tipo_resposta": "nota",
                            "nota_media": sum(valores) / len(valores) if valores else None,
                            "respostas_texto": [],
                        }
                    )
                else:
                    criterios_resp.append(
                        {
                            "criterio_id": criterio_id,
                            "label": criterio.label,
                            "tipo_resposta": "texto",
                            "nota_media": None,
                            "respostas_texto": [n.resposta_texto for n in notas if n.resposta_texto],
                        }
                    )

            lotes_resp.append(
                {
                    "lote_id": lid,
                    "lote_nome": lote.nome if lote else None,
                    "tipo": lote.tipo if lote else None,
                    "nota_geral_media": sum(notas_geral) / len(notas_geral) if notas_geral else None,
                    "quantidade_avaliadores": len(avals),
                    "criterios": criterios_resp,
                    "comentarios": comentarios,
                }
            )

        return {"usuario_id": usuario_id, "lotes": lotes_resp}
