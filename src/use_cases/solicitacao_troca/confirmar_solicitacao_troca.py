from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.solicitacao_troca_repository import SolicitacaoTrocaRepository
from src.use_cases.solicitacao_troca.get_solicitacao_troca import serializar_solicitacao_troca
from src.utils.banca_status import aceita_inscricao, calcular_status_banca
from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase
from src.utils.composicao_banca import ComposicaoBancaChecker
from src.utils.equipe_banca import membros_da_banca
from src.utils.exceptions import RegraDeNegocioError
from src.utils.notificar import notificar


class ConfirmarSolicitacaoTrocaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SolicitacaoTrocaRepository(db)
        self.vendedor_repository = ProjetoVendedorRepository(db)
        self.banca_repository = BancaRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)

    def execute(self, solicitacao_id: int, usuario_id: int):
        solicitacao = self.repository.get_by_id(solicitacao_id)
        if not solicitacao:
            raise RegraDeNegocioError("Solicitação de troca não encontrada")

        if solicitacao.status != "pendente":
            raise RegraDeNegocioError("Esta solicitação de troca já foi resolvida")

        if solicitacao.usuario_original_id == usuario_id:
            raise RegraDeNegocioError("Você não pode confirmar a própria solicitação de troca")

        if solicitacao.usuario_convidado_id is not None and solicitacao.usuario_convidado_id != usuario_id:
            raise RegraDeNegocioError("Esta troca foi enviada como convite para outra pessoa")

        banca = self.banca_repository.get_by_id(solicitacao.banca_id)
        status = calcular_status_banca(banca.data_hora, banca.realizado_em)
        if not aceita_inscricao(status):
            raise RegraDeNegocioError("Não é possível confirmar: esta banca não aceita mais inscrições")

        # Mesma regra de `create_candidatura`: ninguém assume vaga na banca do
        # próprio grupo, e não dá pra confirmar se já é candidato.
        #
        # ⚠ Pela MESMA fonte que ela usa. Enquanto isto olhava só a legada
        # `equipe_projeto`, a última porta ficava aberta: mesmo com o convite
        # barrado na criação, um pedido ABERTO ainda podia ser confirmado por
        # quem é da equipe do projeto — e banca de cronograma não escreve
        # naquela tabela.
        eh_do_grupo = usuario_id in membros_da_banca(
            banca,
            self.banca_escopo_repository,
            self.escopo_repository,
            self.membro_repository,
            self.equipe_projeto_repository,
            self.vendedor_repository,
        )
        if eh_do_grupo:
            raise RegraDeNegocioError("Você não pode confirmar a troca de uma banca do seu próprio grupo")

        candidaturas = self.candidatura_repository.get_by_banca(banca.id)
        ja_candidato = any(c.usuario_id == usuario_id for c in candidaturas)
        if ja_candidato:
            raise RegraDeNegocioError("Você já é candidato desta banca")

        # ⭐ §8: a troca é a terceira porta que põe gente numa banca, e os
        # TETOS por frente valem nela também (2026-09-02). Sem isto, a regra
        # que `create_candidatura` passou a cobrar seria contornável — bastava
        # entrar por uma troca em vez da inscrição.
        recusa = self._recusa_por_teto(banca, candidaturas, solicitacao, usuario_id)
        if recusa:
            raise RegraDeNegocioError(f"Não é possível confirmar a troca: {recusa}")

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

    def _recusa_por_teto(self, banca, candidaturas, solicitacao, usuario_id: int):
        """A frase de recusa dos tetos por frente, ou `None` quando cabe.

        ⚠ **Quem sai da banca sai da conta primeiro.** A troca é uma
        substituição: o número de pessoas não muda, mas a FRENTE muda, e
        contar o que sai junto com o que entra recusaria trocas que só
        devolvem a vaga (o consultor de Business que passa a vaga para outro
        de Business estouraria o teto de Business por um).
        """
        vinculos = self.banca_frente_repository.get_by_banca(banca.id)
        if not vinculos:
            # Banca legada, sem frente vinculada: não há combinação, não há
            # teto por frente a cobrar.
            return None
        atuais = {c.usuario_id for c in candidaturas} - {solicitacao.usuario_original_id}
        regras = ResolverComposicaoUseCase(self.db).para([v.frente_id for v in vinculos])
        return ComposicaoBancaChecker(self.db).recusa_por_teto(
            banca, regras, atuais, usuario_id
        )
