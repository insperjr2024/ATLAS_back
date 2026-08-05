"""Serialização dos escopos vendidos, com a contagem do §5.4 já calculada.

O front nunca recalcula dias — recebe `consumidos`/`restantes` prontos. É o
mesmo princípio de `kickoff_pendente` em `serializar_projeto_resumo`: regra
derivada mora no backend, para as telas não divergirem entre si.
"""

from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.contagem_dias import calcular_contagem_projeto


def nome_do_escopo(escopo, catalogo_por_id: Dict[int, object]) -> str:
    """"Outro" = nome digitado; senão, o nome do catálogo.

    Derivado na leitura, nunca gravado duas vezes — renomear o catálogo não
    deixa cópias velhas para trás.
    """
    if escopo.nome_customizado:
        return escopo.nome_customizado
    do_catalogo = catalogo_por_id.get(escopo.escopo_id)
    return do_catalogo.nome if do_catalogo else "(escopo removido)"


class ListEscoposProjetoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoEscopoRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)

    def execute(self, projeto_id: int, referencia: Optional[date] = None) -> List[dict]:
        escopos = self.repository.get_by_projeto(projeto_id)
        if not escopos:
            return []

        # Carrega o banco UMA vez e passa para as funções puras — é o contrato
        # que `dias_uteis.py` estabelece no docstring.
        historico = self.historico_repository.get_by_projeto(projeto_id)
        dias_nao_letivos = [d.data for d in self.dia_nao_letivo_repository.get_all()]
        catalogo = {e.id: e for e in self.catalogo_repository.get_all()}
        bancas = self.banca_repository.mapa_por_escopo([e.id for e in escopos])
        # Uma banca pode cobrir vários escopos — a tela mostra isso em cada
        # linha ("esta banca também avalia X"), então os ids vêm junto.
        escopos_da_banca = self.banca_escopo_repository.get_escopo_ids_por_banca(
            {b.id for b in bancas.values()}
        )

        contagens = calcular_contagem_projeto(
            escopos, historico, dias_nao_letivos, referencia=referencia
        )

        return [
            serializar_escopo(
                e,
                contagens[e.id],
                catalogo,
                bancas.get(e.id),
                escopos_da_banca,
            )
            for e in escopos
        ]


def serializar_escopo(escopo, contagem, catalogo_por_id, banca=None, escopos_da_banca=None) -> dict:
    return {
        "id": escopo.id,
        "projeto_id": escopo.projeto_id,
        "escopo_id": escopo.escopo_id,
        "nome_customizado": escopo.nome_customizado,
        "nome": nome_do_escopo(escopo, catalogo_por_id),
        "frente_id": escopo.frente_id,
        "dias_uteis_vendidos": escopo.dias_uteis_vendidos,
        "status": escopo.status,
        "data_inicio": escopo.data_inicio,
        "data_entrega_planejada": escopo.data_entrega_planejada,
        "data_entrega_real": escopo.data_entrega_real,
        "tipo_atraso_entrega": escopo.tipo_atraso_entrega,
        "cronograma_oficializado_em": escopo.cronograma_oficializado_em,
        # A contagem do §5.4, calculada — o front só desenha a barra.
        "consumidos": contagem.consumidos,
        "restantes": contagem.restantes,
        "estourou": contagem.estourou,
        "em_contagem": contagem.em_contagem,
        # 🔒 A trava do §5.5 na forma que a tela precisa: o cadeado só abre
        # quando a banca do escopo saiu aprovada.
        "banca": (
            {
                "id": banca.id,
                "data_hora": banca.data_hora,
                "realizado_em": banca.realizado_em,
                "resultado": banca.resultado,
                "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
                # Todos os escopos que esta banca cobre, este incluído.
                "escopo_ids": (escopos_da_banca or {}).get(banca.id, [escopo.id]),
            }
            if banca
            else None
        ),
        "entrega_liberada": bool(banca and banca.resultado == "aprovada"),
    }
