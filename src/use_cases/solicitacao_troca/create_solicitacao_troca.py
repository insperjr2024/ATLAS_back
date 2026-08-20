from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.solicitacao_troca_repository import SolicitacaoTrocaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.solicitacao_troca.get_solicitacao_troca import serializar_solicitacao_troca
from src.utils.banca_status import aceita_inscricao, calcular_status_banca
from src.utils.equipe_banca import membros_da_banca
from src.utils.exceptions import RegraDeNegocioError
from src.utils.notificar import notificar


class CreateSolicitacaoTrocaRequest(BaseModel):
    candidatura_id: int
    #: Nulo = pedido aberto pro pool de elegíveis (comportamento de sempre).
    #: Preenchido = convite direto pra essa pessoa — só ela pode confirmar,
    #: e só ela é notificada (não o pool inteiro).
    usuario_convidado_id: Optional[int] = None


class CreateSolicitacaoTrocaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.candidatura_repository = CandidaturaRepository(db)
        self.vendedor_repository = ProjetoVendedorRepository(db)
        self.banca_repository = BancaRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
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

        convidado_id = request.usuario_convidado_id
        if convidado_id is not None:
            self._validar_convidado(banca, usuario_id, convidado_id)

        solicitacao = self.repository.create(
            banca_id=banca.id,
            usuario_original_id=usuario_id,
            candidatura_id=candidatura.id,
            criado_em=datetime.now(),
            usuario_convidado_id=convidado_id,
        )
        if convidado_id is not None:
            self._notificar_convidado(banca, convidado_id)
        else:
            self._notificar_elegiveis(banca)
        return serializar_solicitacao_troca(solicitacao)

    def _excluidos(self, banca) -> set:
        """Quem NÃO pode confirmar esta troca (§8): já candidato desta banca,
        coordenador ou equipe do próprio projeto. Mesma regra usada pro pool
        aberto e pra validar um convite específico.

        ⚠ Isto lia SÓ `equipe_projeto`, a tabela legada — e banca marcada pelo
        cronograma não escreve nela. Na prática a metade "ou é do grupo do
        projeto" da mensagem de recusa era mentira: dava para convidar um
        consultor da própria equipe, ele aceitava, e virava avaliador do
        projeto dele. Era um contorno para a regra que `create_candidatura`
        cobra no caminho normal — que já usa `membros_da_banca` justamente
        porque tropeçou nisto antes.
        """
        excluidos = {c.usuario_id for c in self.candidatura_repository.get_by_banca(banca.id)}
        excluidos.update(
            membros_da_banca(
                banca,
                self.banca_escopo_repository,
                self.escopo_repository,
                self.membro_repository,
                self.equipe_projeto_repository,
                self.vendedor_repository,
            )
        )
        return excluidos

    def _validar_convidado(self, banca, usuario_id: int, convidado_id: int) -> None:
        if convidado_id == usuario_id:
            raise RegraDeNegocioError("Você não pode convidar a si mesmo para a troca")
        convidado = self.usuario_repository.get_by_id(convidado_id)
        if not convidado or not convidado.ativo:
            raise RegraDeNegocioError("Pessoa convidada não encontrada ou inativa")
        if convidado_id in self._excluidos(banca):
            raise RegraDeNegocioError(
                "Esta pessoa não pode ser convidada: já é candidata desta banca ou é do grupo do projeto"
            )

    def _notificar_convidado(self, banca, convidado_id: int) -> None:
        notificar(
            self.db,
            convidado_id,
            f"Você foi convidado a assumir uma vaga na banca de {banca.nome_projeto}.",
            banca_id=banca.id,
            tipo="troca_banca",
        )

    def _notificar_elegiveis(self, banca) -> None:
        """Pedido aberto para qualquer elegível (§8) — avisa quem PODERIA
        confirmar, mesma regra de exclusão de `confirmar_solicitacao_troca`
        (fora do grupo do projeto, ainda não candidato desta banca)."""
        excluidos = self._excluidos(banca)
        mensagem = f"Há uma solicitação de troca aberta para a banca de {banca.nome_projeto}."
        for usuario in self.usuario_repository.get_ativos():
            if usuario.id not in excluidos:
                notificar(self.db, usuario.id, mensagem, banca_id=banca.id, tipo="troca_banca")
