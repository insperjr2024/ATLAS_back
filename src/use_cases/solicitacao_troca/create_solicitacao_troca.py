from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.solicitacao_troca_repository import SolicitacaoTrocaRepository
from src.use_cases.solicitacao_troca.get_solicitacao_troca import serializar_solicitacao_troca
from src.utils.banca_status import aceita_inscricao, calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError


class CreateSolicitacaoTrocaRequest(BaseModel):
    candidatura_id: int


class CreateSolicitacaoTrocaUseCase:
    def __init__(self, db: Session):
        self.candidatura_repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.repository = SolicitacaoTrocaRepository(db)

    def execute(self, request: CreateSolicitacaoTrocaRequest, usuario_id: int):
        candidatura = self.candidatura_repository.get_by_id(request.candidatura_id)
        if not candidatura:
            raise RegraDeNegocioError("Candidatura não encontrada")

        if candidatura.usuario_id != usuario_id:
            raise RegraDeNegocioError("Você só pode pedir troca da sua própria candidatura")

        banca = self.banca_repository.get_by_id(candidatura.banca_id)
        status = calcular_status_banca(banca.data_hora, banca.realizado_em)
        if not aceita_inscricao(status):
            raise RegraDeNegocioError("Não é possível pedir troca: esta banca não aceita mais inscrições")

        ja_pendente = any(
            s.status == "pendente" for s in self.repository.get_by_candidatura(candidatura.id)
        )
        if ja_pendente:
            raise RegraDeNegocioError("Já existe uma solicitação de troca pendente para esta candidatura")

        solicitacao = self.repository.create(
            banca_id=banca.id,
            usuario_original_id=usuario_id,
            candidatura_id=candidatura.id,
            criado_em=datetime.now(),
        )
        return serializar_solicitacao_troca(solicitacao)
