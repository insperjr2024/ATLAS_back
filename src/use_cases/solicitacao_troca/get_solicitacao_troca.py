from sqlalchemy.orm import Session
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.solicitacao_troca_repository import SolicitacaoTrocaRepository
from src.utils.contexto_troca import calcular_contexto_troca
from src.utils.equipe_banca import membros_da_banca


def serializar_solicitacao_troca(s):
    return {
        "id": s.id,
        "banca_id": s.banca_id,
        "usuario_original_id": s.usuario_original_id,
        "candidatura_id": s.candidatura_id,
        "usuario_convidado_id": s.usuario_convidado_id,
        "status": s.status,
        "criado_em": s.criado_em,
        "confirmada_por": s.confirmada_por,
        "confirmada_em": s.confirmada_em,
    }


def serializar_solicitacao_troca_completa(db: Session, s):
    """`serializar_solicitacao_troca` + o contexto da vaga (2026-09-15, a
    pedido): qual frente é, se a vaga é precisada e quem pode de fato
    confirmar. Calculado na hora, não gravado na solicitação — a composição
    da banca muda depois que o pedido é aberto, e o número tem que refletir
    o estado ATUAL, não uma foto de quando alguém pediu a troca.

    Só computado pra pedido PENDENTE: uma vez resolvida ou cancelada, o
    contexto não importa mais pra ninguém decidir se confirma."""
    base = serializar_solicitacao_troca(s)
    if s.status != "pendente":
        base.update(frente_id=None, frente_nome=None, vaga_precisada=False,
                     precisa_lideranca=False, elegiveis_ids=[])
        return base

    banca = BancaRepository(db).get_by_id(s.banca_id)
    excluidos = {c.usuario_id for c in CandidaturaRepository(db).get_by_banca(s.banca_id)}
    excluidos.update(
        membros_da_banca(
            banca,
            BancaEscopoRepository(db),
            ProjetoEscopoRepository(db),
            ProjetoMembroRepository(db),
            EquipeProjetoRepository(db),
        )
    )
    contexto = calcular_contexto_troca(db, banca, s.usuario_original_id, excluidos)
    elegiveis = [s.usuario_convidado_id] if s.usuario_convidado_id is not None else contexto.elegiveis_ids
    base.update(
        frente_id=contexto.frente_id,
        frente_nome=contexto.frente_nome,
        vaga_precisada=contexto.vaga_precisada,
        precisa_lideranca=contexto.precisa_lideranca,
        elegiveis_ids=elegiveis,
    )
    return base


class ListSolicitacoesTrocaUseCase:
    """Lista tudo — o front filtra "as que eu poderia confirmar" e "as
    minhas", igual o resto do app filtra listas pequenas no cliente.

    ⚠ `elegiveis_ids` (2026-09-15) é o que torna esse filtro correto: antes
    o front só sabia excluir quem já é candidato/do grupo, sem saber que uma
    vaga de frente específica só um subconjunto pode cobrir."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = SolicitacaoTrocaRepository(db)

    def execute(self):
        return [
            serializar_solicitacao_troca_completa(self.db, s)
            for s in self.repository.get_all()
        ]
