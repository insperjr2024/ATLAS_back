from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.banca_repository import BancaRepository
from src.use_cases.notificacao.eventos import notificar_escalacao_banca
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError


class UpdateCandidaturaRequest(BaseModel):
    banca_id: Optional[int] = None
    confirmado: Optional[bool] = None


class UpdateCandidaturaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, candidatura_id: int, request: UpdateCandidaturaRequest):
        data = request.dict(exclude_unset=True)
        confirmava_antes = getattr(self.repository.get_by_id(candidatura_id), "confirmado", None)
        candidatura = self.repository.update(candidatura_id, **data)
        if not candidatura:
            return None

        # Só na virada para confirmado: um PATCH que não mexe em `confirmado`
        # (ou que reconfirma o que já estava) não é notícia nenhuma.
        if candidatura.confirmado and not confirmava_antes:
            banca = self.banca_repository.get_by_id(candidatura.banca_id)
            if banca:
                notificar_escalacao_banca(
                    self.db,
                    banca.id,
                    candidatura.usuario_id,
                    banca.nome_projeto,
                    banca.data_hora,
                )

        return {
            "id": candidatura.id,
            "banca_id": candidatura.banca_id,
            "usuario_id": candidatura.usuario_id,
            "criado_em": candidatura.criado_em,
            "confirmado": candidatura.confirmado
        }


class DeleteCandidaturaUseCase:
    def __init__(self, db: Session):
        self.repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, candidatura_id: int) -> bool:
        candidatura = self.repository.get_by_id(candidatura_id)
        if not candidatura:
            return False

        # Mesma virada do create: só a realização tranca. Antes da F5, uma
        # banca que escorregava deixava as pessoas presas na inscrição.
        banca = self.banca_repository.get_by_id(candidatura.banca_id)
        if banca and calcular_status_banca(banca.data_hora, banca.realizado_em, cancelada_em=getattr(banca, "cancelada_em", None)) == "realizada":
            raise RegraDeNegocioError("Não é possível se desalocar: esta banca já foi realizada")

        return self.repository.delete(candidatura_id)