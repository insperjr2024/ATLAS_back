from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.solicitacao_troca_repository import SolicitacaoTrocaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.solicitacao_troca.get_solicitacao_troca import serializar_solicitacao_troca
from src.utils.banca_status import aceita_inscricao, calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError
from src.utils.notificar import notificar


class CreateSolicitacaoTrocaRequest(BaseModel):
    candidatura_id: int


class CreateSolicitacaoTrocaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.candidatura_repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)
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
        self._notificar_elegiveis(banca)
        return serializar_solicitacao_troca(solicitacao)

    def _notificar_elegiveis(self, banca) -> None:
        """Pedido aberto para qualquer elegível (§8) — avisa quem PODERIA
        confirmar, mesma regra de exclusão de `confirmar_solicitacao_troca`
        (fora do grupo do projeto, ainda não candidato desta banca)."""
        excluidos = {c.usuario_id for c in self.candidatura_repository.get_by_banca(banca.id)}
        excluidos.add(banca.coordenador_id)
        excluidos.update(e.usuario_id for e in self.equipe_projeto_repository.get_by_banca(banca.id))

        mensagem = f"Há uma solicitação de troca aberta para a banca de {banca.nome_projeto}."
        for usuario in self.usuario_repository.get_ativos():
            if usuario.id not in excluidos:
                notificar(self.db, usuario.id, mensagem, banca_id=banca.id, tipo="troca_banca")
