"""Abrir ou fechar a avaliação de uma banca na mão (2026-10-06, a pedido).

Pontual: a diretoria reabre por exceção pra quem esqueceu de avaliar no
prazo, ou fecha antes. Nulo volta ao automático. Ver
`utils/avaliacoes_pendentes.avaliacao_aberta`.
"""

from typing import Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.utils.avaliacoes_pendentes import avaliacao_aberta, prazo_avaliacao
from src.utils.exceptions import RegraDeNegocioError


class PrazoAvaliacaoRequest(BaseModel):
    override: Optional[Literal["aberto", "fechado"]] = None


class DefinirPrazoAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, request: PrazoAvaliacaoRequest) -> dict:
        banca = self.repository.get_by_id(banca_id)
        if not banca:
            raise RegraDeNegocioError("Banca não encontrada")
        if not banca.realizado_em:
            raise RegraDeNegocioError("Esta banca ainda não foi realizada; não há avaliação pra abrir ou fechar.")
        banca = self.repository.update(banca_id, prazo_avaliacao_override=request.override)
        return {
            "id": banca.id,
            "prazo_avaliacao_override": banca.prazo_avaliacao_override,
            "prazo_avaliacao": prazo_avaliacao(banca),
            "avaliacao_aberta": avaliacao_aberta(banca),
        }
