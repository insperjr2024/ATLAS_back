import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.desempenho_avaliacao_repository import DesempenhoAvaliacaoRepository
from src.repositories.desempenho_criterio_repository import DesempenhoCriterioRepository
from src.repositories.desempenho_formulario_repository import DesempenhoFormularioRepository
from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.desempenho_avaliacao.get_fila import FORM_TYPE_ESCOPO
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
        # Mesma régua de `get_fila.py`: só conta se o formulário tem
        # conteúdo, e nunca derruba o resto da conta se algo aqui falhar.
        escopo_por_projeto: dict[int, list[int]] = {}
        try:
            form_escopo = (
                self.formulario_repo.first_by(tipo="finalizacao", papel=FORM_TYPE_ESCOPO)
                if lote.tipo == "finalizacao"
                and getattr(lote, "inclui_avaliacao_de_escopo", True)
                else None
            )
            tem_conteudo = form_escopo and self.criterio_repo.get_by_formulario(form_escopo.id)
            if tem_conteudo:
                for membro in membros:
                    escopo_por_projeto.setdefault(membro.usuario_id, []).append(membro.projeto_id)
        except Exception:
            logger.exception("Falha ao montar pendências de Avaliação do Escopo (lote %s)", lote_id)

        usuario_ids = {uid for par in agregados for uid in par} | set(escopo_por_projeto)
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
                    "respondida": self.avaliacao_repo.existe_par(lote_id, avaliador_id, avaliado_id),
                }
            )
        for usuario_id, ids_projeto in escopo_por_projeto.items():
            resultado.append(
                {
                    "avaliador_id": usuario_id,
                    "avaliador_nome": nomes.get(usuario_id),
                    "avaliado_id": usuario_id,
                    "avaliado_nome": nomes.get(usuario_id),
                    "form_type": FORM_TYPE_ESCOPO,
                    "projeto_ids": ids_projeto,
                    "projeto_nomes": [nomes_projeto.get(pid) for pid in ids_projeto],
                    "respondida": self.avaliacao_repo.existe_par(lote_id, usuario_id, usuario_id),
                }
            )
        return resultado
