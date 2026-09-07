from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.use_cases.desempenho_lote.get_lote import serializar_lote
from src.utils.desempenho_cascata import aplicar_cascata_finalizacao


class CreateDesempenhoLoteRequest(BaseModel):
    nome: str
    tipo: Literal["periodico", "finalizacao"]
    data_inicio: datetime
    data_fim: datetime
    projeto_ids: List[int]
    #: ⭐ Só a finalização automática preenche (2026-09-05) — é a referência
    #: que `CancelarBancaUseCase` usa pra desfazer o lote certo se a banca
    #: for cancelada depois de já realizada. Nunca vem da tela de Formulários
    #: (lote aberto à mão não tem banca de origem).
    banca_id: Optional[int] = None


class CreateDesempenhoLoteUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)

    def execute(self, request: CreateDesempenhoLoteRequest) -> dict:
        lote = self.lote_repo.create(
            nome=request.nome,
            tipo=request.tipo,
            data_inicio=request.data_inicio,
            data_fim=request.data_fim,
            override_manual=None,
            banca_id=request.banca_id,
        )
        if request.projeto_ids:
            self.lote_projeto_repo.bulk_create(
                [{"lote_id": lote.id, "projeto_id": pid} for pid in request.projeto_ids]
            )

        # Regra 2.2: finalização "rouba" o projeto de qualquer periódica aberta.
        if request.tipo == "finalizacao" and request.projeto_ids:
            aplicar_cascata_finalizacao(self.db, request.projeto_ids)

        return serializar_lote(lote, request.projeto_ids)
