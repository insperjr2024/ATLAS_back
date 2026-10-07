import logging

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
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.desempenho_escopo import (
    FORM_TYPE_ESCOPO,
    catalogo_de_escopos,
    escopos_avaliaveis_no_lote,
    escopos_da_pessoa,
    formulario_escopo_do_lote,
    nome_do_escopo_vendido,
)
from src.utils.desempenho_fila import calcular_pares_lote, deduplicar_pares
from src.utils.desempenho_lote import esta_aberto

logger = logging.getLogger(__name__)

# `FORM_TYPE_ESCOPO` mora em `utils/desempenho_escopo.py` desde 2026-10-05;
# fica reexportado aqui porque `get_pendencias` e `create_avaliacao` o
# importavam deste módulo.
__all__ = ["FORM_TYPE_ESCOPO", "GetFilaUsuarioUseCase"]


class GetFilaUsuarioUseCase:
    """Quem `usuario_id` ainda precisa avaliar, olhando os lotes abertos (e os
    fechados há pouco tempo, regra 2.3-bis) cujo projeto ele integra hoje.
    Reaproveitada tanto pelo endpoint de fila do próprio usuário quanto para
    calcular a `proxima_pendencia` depois de submeter uma avaliação (regra
    2.4) — nesse segundo uso os itens fechados não atrapalham porque quem
    chama já filtra pelo `lote_id` que acabou de responder."""

    def __init__(self, db: Session):
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)
        self.membro_repo = ProjetoMembroRepository(db)
        self.avaliacao_repo = DesempenhoAvaliacaoRepository(db)
        self.usuario_repo = UsuarioRepository(db)
        self.formulario_repo = DesempenhoFormularioRepository(db)
        self.criterio_repo = DesempenhoCriterioRepository(db)
        self.lote_formulario_repo = DesempenhoLoteFormularioRepository(db)
        self.projeto_escopo_repo = ProjetoEscopoRepository(db)
        self.banca_escopo_repo = BancaEscopoRepository(db)
        self.usuario_frente_repo = UsuarioFrenteRepository(db)
        self.escopo_repo = EscopoRepository(db)

    def execute(self, usuario_id: int) -> list[dict]:
        meus_projetos_ativos = {
            m.projeto_id for m in self.membro_repo.get_atuais_por_usuario(usuario_id)
        }
        minhas_frentes = {uf.frente_id for uf in self.usuario_frente_repo.get_by_usuario(usuario_id)}
        resultado = []

        for lote in self.lote_repo.get_relevantes_para_fila():
            projeto_ids = self.lote_projeto_repo.get_projeto_ids(lote.id)
            if not (meus_projetos_ativos & set(projeto_ids)):
                continue

            membros = self.membro_repo.get_by_projetos(projeto_ids, apenas_atuais=True)
            agregados = deduplicar_pares(calcular_pares_lote(membros, lote.criado_em))
            lote_aberto = esta_aberto(lote.override_manual, lote.data_inicio, lote.data_fim)

            # Avaliação do Escopo (2026-09-09): itens de fila ADITIVOS, um
            # POR ESCOPO da minha frente (2026-10-05). Na finalização fala dos
            # escopos da banca; na periódica, dos em andamento. Envolto em
            # try/except: se qualquer coisa aqui falhar, ou o formulário não
            # estiver configurado, a fila normal (pares) segue intacta. Ver
            # `utils/desempenho_escopo.py`.
            try:
                form_escopo = formulario_escopo_do_lote(
                    lote, self.formulario_repo, self.criterio_repo, self.lote_formulario_repo
                )
                meus_escopos = (
                    escopos_da_pessoa(
                        usuario_id,
                        escopos_avaliaveis_no_lote(
                            lote, projeto_ids, self.projeto_escopo_repo, self.banca_escopo_repo
                        ),
                        membros,
                        minhas_frentes,
                    )
                    if form_escopo
                    else []
                )
                pendentes = [
                    pe
                    for pe in meus_escopos
                    if not self.avaliacao_repo.respondeu_escopo(lote.id, usuario_id, pe.id)
                ]
                if pendentes:
                    eu = self.usuario_repo.get_by_id(usuario_id)
                    catalogo = catalogo_de_escopos(self.escopo_repo, pendentes)
                    for pe in pendentes:
                        resultado.append(
                            {
                                "lote_id": lote.id,
                                "lote_nome": lote.nome,
                                "lote_tipo": lote.tipo,
                                "aberto": lote_aberto,
                                "avaliado_id": usuario_id,
                                "avaliado_nome": eu.nome if eu else None,
                                "form_type": FORM_TYPE_ESCOPO,
                                "projeto_ids": [pe.projeto_id],
                                "projeto_escopo_id": pe.id,
                                "escopo_nome": nome_do_escopo_vendido(pe, catalogo),
                            }
                        )
            except Exception:
                logger.exception(
                    "Falha ao montar item de Avaliação do Escopo (lote %s, usuário %s)",
                    lote.id,
                    usuario_id,
                )

            for (avaliador_id, avaliado_id), dados in agregados.items():
                if avaliador_id != usuario_id:
                    continue
                if self.avaliacao_repo.existe_par(lote.id, avaliador_id, avaliado_id):
                    continue
                avaliado = self.usuario_repo.get_by_id(avaliado_id)
                resultado.append(
                    {
                        "lote_id": lote.id,
                        "lote_nome": lote.nome,
                        "lote_tipo": lote.tipo,
                        "aberto": lote_aberto,
                        "avaliado_id": avaliado_id,
                        "avaliado_nome": avaliado.nome if avaliado else None,
                        "form_type": dados["form_type"],
                        "projeto_ids": dados["projeto_ids"],
                        "projeto_escopo_id": None,
                        "escopo_nome": None,
                    }
                )
        return resultado
