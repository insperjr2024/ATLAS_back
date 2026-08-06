from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.solicitacao_troca_repository import SolicitacaoTrocaRepository
from src.use_cases.solicitacao_troca.get_solicitacao_troca import serializar_solicitacao_troca
from src.utils.banca_status import aceita_inscricao, calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError
from src.utils.notificar import notificar


class ConfirmarSolicitacaoTrocaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SolicitacaoTrocaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)

    def execute(self, solicitacao_id: int, usuario_id: int):
        solicitacao = self.repository.get_by_id(solicitacao_id)
        if not solicitacao:
            raise RegraDeNegocioError("Solicitação de troca não encontrada")

        if solicitacao.status != "pendente":
            raise RegraDeNegocioError("Esta solicitação de troca já foi resolvida")

        if solicitacao.usuario_original_id == usuario_id:
            raise RegraDeNegocioError("Você não pode confirmar a própria solicitação de troca")

        banca = self.banca_repository.get_by_id(solicitacao.banca_id)
        status = calcular_status_banca(banca.data_hora, banca.realizado_em)
        if not aceita_inscricao(status):
            raise RegraDeNegocioError("Não é possível confirmar: esta banca não aceita mais inscrições")

        # Mesma regra de `create_candidatura`: ninguém assume vaga na banca do
        # próprio grupo, e não dá pra confirmar se já é candidato.
        eh_do_grupo = banca.coordenador_id == usuario_id or any(
            e.usuario_id == usuario_id for e in self.equipe_projeto_repository.get_by_banca(banca.id)
        )
        if eh_do_grupo:
            raise RegraDeNegocioError("Você não pode confirmar a troca de uma banca do seu próprio grupo")

        ja_candidato = any(
            c.usuario_id == usuario_id for c in self.candidatura_repository.get_by_banca(banca.id)
        )
        if ja_candidato:
            raise RegraDeNegocioError("Você já é candidato desta banca")

        agora = datetime.now()
        # Ordem de propósito: marcar a solicitação `confirmada` primeiro
        # garante que o histórico fica correto mesmo que algo falhe logo
        # depois; a candidatura antiga só é apagada por último.
        self.repository.update(solicitacao.id, status="confirmada", confirmada_por=usuario_id, confirmada_em=agora)
        self.candidatura_repository.create(banca_id=banca.id, usuario_id=usuario_id, criado_em=agora, confirmado=False)
        if solicitacao.candidatura_id:
            self.candidatura_repository.delete(solicitacao.candidatura_id)

        notificar(
            self.db,
            solicitacao.usuario_original_id,
            f"Sua troca para a banca de {banca.nome_projeto} foi confirmada.",
            banca_id=banca.id,
            tipo="troca_banca",
        )

        return serializar_solicitacao_troca(self.repository.get_by_id(solicitacao.id))
