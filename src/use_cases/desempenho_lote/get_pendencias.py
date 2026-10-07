import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.desempenho_avaliacao_repository import DesempenhoAvaliacaoRepository
from src.repositories.desempenho_criterio_repository import DesempenhoCriterioRepository
from src.repositories.desempenho_formulario_repository import DesempenhoFormularioRepository
from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_formulario_repository import DesempenhoLoteFormularioRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.desempenho_escopo import (
    FORM_TYPE_ESCOPO,
    catalogo_de_escopos,
    escopos_avaliaveis_no_lote,
    escopos_da_pessoa,
    formulario_escopo_do_lote,
    frentes_por_usuario,
    nome_do_escopo_vendido,
)
from src.utils.desempenho_fila import calcular_pares_lote, deduplicar_pares

logger = logging.getLogger(__name__)


class GetPendenciasLoteUseCase:
    def __init__(self, db: Session):
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)
        self.membro_repo = ProjetoMembroRepository(db)
        self.avaliacao_repo = DesempenhoAvaliacaoRepository(db)
        self.usuario_repo = UsuarioRepository(db)
        self.projeto_repo = ProjetoRepository(db)
        self.formulario_repo = DesempenhoFormularioRepository(db)
        self.criterio_repo = DesempenhoCriterioRepository(db)
        self.lote_formulario_repo = DesempenhoLoteFormularioRepository(db)
        self.projeto_escopo_repo = ProjetoEscopoRepository(db)
        self.banca_escopo_repo = BancaEscopoRepository(db)
        self.usuario_frente_repo = UsuarioFrenteRepository(db)
        self.escopo_repo = EscopoRepository(db)

    def execute(self, lote_id: int) -> Optional[list[dict]]:
        lote = self.lote_repo.get_by_id(lote_id)
        if not lote:
            return None

        projeto_ids = self.lote_projeto_repo.get_projeto_ids(lote_id)
        membros = self.membro_repo.get_by_projetos(projeto_ids, apenas_atuais=True)
        agregados = deduplicar_pares(calcular_pares_lote(membros, lote.criado_em))

        # ⭐ Avaliação do Escopo (2026-09-24, corrigido): `calcular_pares_lote`
        # pula avaliador == avaliado de propósito (não é par), então essa
        # auto-avaliação nunca entrava aqui — a fila PESSOAL de cada um
        # (`get_fila.py`) já soma esse item há tempos, mas o painel de
        # pendências (e as notificações que nascem dele, que reusam
        # `pendencias`) nunca souberam que ela existia. Resultado: a
        # diretoria via "Fulano falta avaliar Beltrano" mas nunca "falta
        # avaliar Escopo", mesmo com o lote e o formulário prontos pra isso.
        # Mesma régua de `get_fila.py` (`utils/desempenho_escopo.py`): só
        # conta se o formulário tem conteúdo, um item POR ESCOPO da frente da
        # pessoa (2026-10-05), e nunca derruba o resto da conta se algo aqui
        # falhar.
        escopos_por_pessoa: dict[int, list] = {}
        catalogo: dict[int, str] = {}
        try:
            form_escopo = formulario_escopo_do_lote(lote, self.formulario_repo, self.criterio_repo, self.lote_formulario_repo)
            if form_escopo:
                escopos = escopos_avaliaveis_no_lote(
                    lote, projeto_ids, self.projeto_escopo_repo, self.banca_escopo_repo
                )
                frentes = frentes_por_usuario(self.usuario_frente_repo)
                for usuario_id in {m.usuario_id for m in membros}:
                    meus = escopos_da_pessoa(usuario_id, escopos, membros, frentes.get(usuario_id))
                    if meus:
                        escopos_por_pessoa[usuario_id] = meus
                catalogo = catalogo_de_escopos(self.escopo_repo, escopos)
        except Exception:
            logger.exception("Falha ao montar pendências de Avaliação do Escopo (lote %s)", lote_id)

        usuario_ids = {uid for par in agregados for uid in par} | set(escopos_por_pessoa)
        nomes = {u.id: u.nome for u in self.usuario_repo.get_all() if u.id in usuario_ids}
        nomes_projeto = {p.id: p.nome for p in self.projeto_repo.get_all() if p.id in projeto_ids}

        resultado = []
        for (avaliador_id, avaliado_id), dados in agregados.items():
            resultado.append(
                {
                    "avaliador_id": avaliador_id,
                    "avaliador_nome": nomes.get(avaliador_id),
                    "avaliado_id": avaliado_id,
                    "avaliado_nome": nomes.get(avaliado_id),
                    "form_type": dados["form_type"],
                    "projeto_ids": dados["projeto_ids"],
                    "projeto_nomes": [nomes_projeto.get(pid) for pid in dados["projeto_ids"]],
                    "projeto_escopo_id": None,
                    "escopo_nome": None,
                    "respondida": self.avaliacao_repo.existe_par(lote_id, avaliador_id, avaliado_id),
                }
            )
        for usuario_id, escopos in sorted(escopos_por_pessoa.items()):
            for pe in escopos:
                resultado.append(
                    {
                        "avaliador_id": usuario_id,
                        "avaliador_nome": nomes.get(usuario_id),
                        "avaliado_id": usuario_id,
                        "avaliado_nome": nomes.get(usuario_id),
                        "form_type": FORM_TYPE_ESCOPO,
                        "projeto_ids": [pe.projeto_id],
                        "projeto_nomes": [nomes_projeto.get(pe.projeto_id)],
                        "projeto_escopo_id": pe.id,
                        "escopo_nome": nome_do_escopo_vendido(pe, catalogo),
                        "respondida": self.avaliacao_repo.respondeu_escopo(lote_id, usuario_id, pe.id),
                    }
                )
        return resultado
