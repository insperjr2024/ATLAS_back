"""Quem ficou pendente nos formulários já fechados (2026-10-13, a pedido).

A pendência de um lote aberto ainda pode ser resolvida; a de um lote
fechado virou fato: a pessoa não respondeu. Esta lista junta isso de todos
os fechados, agrupado por pessoa, dizendo em qual formulário cada uma
ficou devendo. É a mesma conta de `GetPendenciasLoteUseCase` (inclusive a
regra da periódica, que tira quem está em frente sem escopo em andamento),
só filtrada pelo que não foi respondido.

"Fechado" é a régua de `esta_aberto` (override ou datas): um lote forçado
"fechado" antes do prazo conta, e um forçado "aberto" depois do prazo não.
"""

from sqlalchemy.orm import Session

from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.use_cases.desempenho_lote.get_pendencias import GetPendenciasLoteUseCase
from src.utils.desempenho_lote import esta_aberto


class ListarPendenciasFechadosUseCase:
    def __init__(self, db: Session):
        self.lote_repo = DesempenhoLoteRepository(db)
        self.pendencias = GetPendenciasLoteUseCase(db)

    def execute(self) -> list[dict]:
        fechados = sorted(
            (
                lote
                for lote in self.lote_repo.get_all()
                if not esta_aberto(lote.override_manual, lote.data_inicio, lote.data_fim)
            ),
            key=lambda lote: lote.data_fim,
            reverse=True,
        )

        por_pessoa: dict[int, dict] = {}
        for lote in fechados:
            pendencias = [p for p in (self.pendencias.execute(lote.id) or []) if not p.get("respondida")]
            if not pendencias:
                continue
            por_lote: dict[int, dict] = {}
            for p in pendencias:
                pessoa = por_pessoa.setdefault(
                    p["avaliador_id"],
                    {"avaliador_id": p["avaliador_id"], "avaliador_nome": p.get("avaliador_nome"), "total": 0, "lotes": []},
                )
                entrada = por_lote.get(p["avaliador_id"])
                if entrada is None:
                    entrada = por_lote[p["avaliador_id"]] = {
                        "lote_id": lote.id,
                        "lote_nome": lote.nome,
                        "lote_tipo": lote.tipo,
                        "fechado_em": lote.data_fim,
                        "pendentes": 0,
                        "itens": [],
                    }
                    pessoa["lotes"].append(entrada)
                entrada["pendentes"] += 1
                pessoa["total"] += 1
                entrada["itens"].append(
                    {
                        "avaliado_nome": p.get("avaliado_nome"),
                        "form_type": p.get("form_type"),
                        "projeto_nomes": p.get("projeto_nomes") or [],
                        "escopo_nome": p.get("escopo_nome"),
                    }
                )

        return sorted(por_pessoa.values(), key=lambda x: (-x["total"], x["avaliador_nome"] or ""))
