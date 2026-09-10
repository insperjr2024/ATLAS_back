from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.desempenho_avaliacao_nota_repository import DesempenhoAvaliacaoNotaRepository
from src.repositories.desempenho_avaliacao_repository import DesempenhoAvaliacaoRepository
from src.repositories.desempenho_criterio_repository import DesempenhoCriterioRepository
from src.repositories.desempenho_formulario_repository import DesempenhoFormularioRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository


def serializar_avaliacao_resumo(a, escopo: Optional[dict] = None) -> dict:
    d = {
        "id": a.id,
        "lote_id": a.lote_id,
        "formulario_id": a.formulario_id,
        "avaliador_id": a.avaliador_id,
        "avaliado_id": a.avaliado_id,
        "nota_geral": a.nota_geral,
        "comentarios": a.comentarios,
        "criado_em": a.criado_em,
    }
    # ⭐ Preenchido só na Avaliação do Escopo (auto-avaliação): QUAL escopo a
    # pessoa avaliou, cruzando a frente dela com os escopos da banca do lote
    # (2026-09-10). `None` quando não dá pra desambiguar. O painel agrupa por
    # isto em vez de por pessoa.
    if escopo is not None:
        d["escopo"] = escopo
    return d


def _sem_frente(e: dict) -> dict:
    return {k: v for k, v in e.items() if k != "frente_id"}


class ListDesempenhoAvaliacoesUseCase:
    def __init__(self, db: Session):
        self.repository = DesempenhoAvaliacaoRepository(db)
        self.lote_repo = DesempenhoLoteRepository(db)
        self.formulario_repo = DesempenhoFormularioRepository(db)
        self.banca_escopo_repo = BancaEscopoRepository(db)
        self.projeto_escopo_repo = ProjetoEscopoRepository(db)
        self.escopo_repo = EscopoRepository(db)
        self.projeto_repo = ProjetoRepository(db)
        self.usuario_frente_repo = UsuarioFrenteRepository(db)

    def execute(self) -> list[dict]:
        avaliacoes = self.repository.get_all()

        form_escopo = self.formulario_repo.first_by(tipo="finalizacao", papel="escopo")
        escopo_form_id = form_escopo.id if form_escopo else None
        if escopo_form_id is None or not any(
            a.formulario_id == escopo_form_id for a in avaliacoes
        ):
            return [serializar_avaliacao_resumo(a) for a in avaliacoes]

        frentes_por_usuario: dict[int, set] = {}
        for uf in self.usuario_frente_repo.get_all():
            frentes_por_usuario.setdefault(uf.usuario_id, set()).add(uf.frente_id)

        escopos_por_lote = self._escopos_por_lote(
            {a.lote_id for a in avaliacoes if a.formulario_id == escopo_form_id}
        )

        def atribuir(a) -> Optional[dict]:
            if a.formulario_id != escopo_form_id:
                return None
            opcoes = escopos_por_lote.get(a.lote_id, [])
            if len(opcoes) == 1:
                return _sem_frente(opcoes[0])
            do_avaliador = frentes_por_usuario.get(a.avaliador_id, set())
            casam = [e for e in opcoes if e["frente_id"] in do_avaliador]
            return _sem_frente(casam[0]) if len(casam) == 1 else None

        return [serializar_avaliacao_resumo(a, escopo=atribuir(a)) for a in avaliacoes]

    def _escopos_por_lote(self, lote_ids: set) -> dict[int, list]:
        """`lote_id -> [{escopo_id, nome, frente_id, projeto_nome}]` — os
        escopos do CATÁLOGO que a banca do lote cobriu."""
        out: dict[int, list] = {}
        for lid in lote_ids:
            lote = self.lote_repo.get_by_id(lid)
            if not lote or not getattr(lote, "banca_id", None):
                continue
            pe_ids = self.banca_escopo_repo.get_escopo_ids(lote.banca_id)
            for pe in self.projeto_escopo_repo.get_by_ids(pe_ids):
                if not pe.escopo_id:
                    continue
                cat = self.escopo_repo.get_by_id(pe.escopo_id)
                if not cat:
                    continue
                projeto = self.projeto_repo.get_by_id(pe.projeto_id)
                out.setdefault(lid, []).append(
                    {
                        "escopo_id": cat.id,
                        "nome": cat.nome,
                        "frente_id": cat.frente_id,
                        "projeto_nome": projeto.nome if projeto else None,
                    }
                )
        return out


class GetDesempenhoAvaliacaoUseCase:
    """Detalhe completo de uma avaliação — quem respondeu, quando, e a nota
    (ou resposta em texto) de cada critério, com o rótulo já resolvido."""

    def __init__(self, db: Session):
        self.avaliacao_repo = DesempenhoAvaliacaoRepository(db)
        self.avaliacao_nota_repo = DesempenhoAvaliacaoNotaRepository(db)
        self.criterio_repo = DesempenhoCriterioRepository(db)

    def execute(self, avaliacao_id: int) -> Optional[dict]:
        avaliacao = self.avaliacao_repo.get_by_id(avaliacao_id)
        if not avaliacao:
            return None

        notas = self.avaliacao_nota_repo.get_by_avaliacao(avaliacao_id)
        notas_resp = []
        for n in notas:
            criterio = self.criterio_repo.get_by_id(n.criterio_id)
            notas_resp.append(
                {
                    "criterio_id": n.criterio_id,
                    "label": criterio.label if criterio else None,
                    "tipo_resposta": criterio.tipo_resposta if criterio else None,
                    "nota": n.nota,
                    "resposta_texto": n.resposta_texto,
                }
            )

        return {**serializar_avaliacao_resumo(avaliacao), "notas": notas_resp}
