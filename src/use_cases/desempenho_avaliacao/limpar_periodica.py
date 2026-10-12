"""Apaga respostas de avaliação periódica que a regra de escopo em andamento
não permite mais (2026-10-12, a pedido).

A regra (`membros_da_periodica`) impede respostas novas fora do recorte. Esta
limpeza cuida das que entraram antes dela: alguém de Tech avaliando ou sendo
avaliado num projeto em que o escopo de Tech nem começou, por exemplo. Essas
notas são ruído (a pessoa dá 5 pra quem não trabalhou com ela) e sujam o
relatório.

Critério, pensado pra nunca apagar resposta que valia:
- avaliação entre pessoas: sai só quando as duas dividem pelo menos um
  projeto do lote e, em TODOS os que dividem, a regra tira uma delas. Conta
  a equipe de qualquer época (inclusive quem já saiu do projeto), então
  mudança de equipe depois do lote não apaga nada;
- Avaliação do Escopo: sai quando o escopo avaliado não estava em andamento
  na data do lote. A antiga, sem escopo gravado, fica.

Só lotes periódicos. `aplicar=False` (padrão) só lista o que sairia.
"""

from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from src.models.desempenho_avaliacao_model import DesempenhoAvaliacaoModel
from src.models.desempenho_lote_model import DesempenhoLoteModel
from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.desempenho_escopo import (
    data_de_referencia,
    em_andamento_em,
    frentes_por_usuario,
    membros_da_periodica,
)


class LimparAvaliacoesForaDaPeriodicaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)
        self.membro_repo = ProjetoMembroRepository(db)
        self.projeto_escopo_repo = ProjetoEscopoRepository(db)
        self.usuario_frente_repo = UsuarioFrenteRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self, aplicar: bool = False, lote_ids: Optional[List[int]] = None) -> List[dict]:
        consulta = self.db.query(DesempenhoLoteModel).filter(DesempenhoLoteModel.tipo == "periodico")
        if lote_ids:
            consulta = consulta.filter(DesempenhoLoteModel.id.in_(lote_ids))
        frentes = frentes_por_usuario(self.usuario_frente_repo)
        nomes = {u.id: u.nome for u in self.usuario_repo.get_all()}

        fora: List[Tuple[DesempenhoAvaliacaoModel, str]] = []
        for lote in consulta.all():
            fora.extend(self._fora_do_lote(lote, frentes))

        relatorio = [
            {
                "avaliacao_id": a.id,
                "lote_id": a.lote_id,
                "avaliador": nomes.get(a.avaliador_id, a.avaliador_id),
                "avaliado": nomes.get(a.avaliado_id, a.avaliado_id),
                "motivo": motivo,
            }
            for a, motivo in fora
        ]
        if aplicar and fora:
            for a, _ in fora:
                self.db.delete(a)
            self.db.commit()
        return relatorio

    def _fora_do_lote(self, lote, frentes: Dict[int, Set[int]]) -> List[Tuple[DesempenhoAvaliacaoModel, str]]:
        projeto_ids = self.lote_projeto_repo.get_projeto_ids(lote.id)
        if not projeto_ids:
            return []
        escopos = self.projeto_escopo_repo.get_by_projetos(projeto_ids)
        todos = self.membro_repo.get_by_projetos(projeto_ids, apenas_atuais=False)
        mantidos = membros_da_periodica(lote, todos, escopos, frentes)

        projetos_de: Dict[int, Set[int]] = {}
        for m in todos:
            projetos_de.setdefault(m.usuario_id, set()).add(m.projeto_id)
        mantido_em: Dict[int, Set[int]] = {}
        for m in mantidos:
            mantido_em.setdefault(m.usuario_id, set()).add(m.projeto_id)

        referencia = data_de_referencia(lote)
        escopo_por_id = {pe.id: pe for pe in escopos}

        fora = []
        avaliacoes = self.db.query(DesempenhoAvaliacaoModel).filter(DesempenhoAvaliacaoModel.lote_id == lote.id).all()
        for a in avaliacoes:
            if a.avaliador_id == a.avaliado_id:
                pe = escopo_por_id.get(a.projeto_escopo_id) if a.projeto_escopo_id else None
                if pe is not None and not em_andamento_em(pe, referencia):
                    fora.append((a, "escopo avaliado não estava em andamento"))
                continue
            em_comum = projetos_de.get(a.avaliador_id, set()) & projetos_de.get(a.avaliado_id, set())
            if not em_comum:
                continue
            validos = mantido_em.get(a.avaliador_id, set()) & mantido_em.get(a.avaliado_id, set()) & em_comum
            if not validos:
                fora.append((a, "frente sem escopo em andamento no projeto"))
        return fora
