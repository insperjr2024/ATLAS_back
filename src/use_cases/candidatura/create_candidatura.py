from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError


class CreateCandidaturaRequest(BaseModel):
    banca_id: int
    usuario_id: int
    criado_em: datetime
    confirmado: bool = False


class CreateCandidaturaUseCase:
    def __init__(self, db: Session):
        self.repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)

    def execute(self, request: CreateCandidaturaRequest):
        banca = self.banca_repository.get_by_id(request.banca_id)
        if not banca:
            raise RegraDeNegocioError("Banca não encontrada")

        if calcular_status_banca(banca.data_hora) == "realizada":
            raise RegraDeNegocioError("Não é possível se candidatar: esta banca já foi realizada")

        candidaturas_existentes = self.repository.get_by_banca(request.banca_id)
        configuracao = self.configuracao_repository.get()
        vagas = configuracao.vagas_por_banca if configuracao else 5

        if len(candidaturas_existentes) >= vagas:
            raise RegraDeNegocioError("Não é possível se candidatar: banca lotada")

        candidatura = self.repository.create(
            banca_id=request.banca_id,
            usuario_id=request.usuario_id,
            criado_em=request.criado_em,
            confirmado=request.confirmado
        )
        return {
            "id": candidatura.id,
            "banca_id": candidatura.banca_id,
            "usuario_id": candidatura.usuario_id,
            "criado_em": candidatura.criado_em,
            "confirmado": candidatura.confirmado
        }