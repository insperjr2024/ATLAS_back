from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.models.projeto_model import ProjetoModel
from src.repositories.banca_repository import BancaRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.utils.ambientacao import fim_da_ambientacao


def serializar_projeto_resumo(
    projeto, frente_repo: ProjetoFrenteRepository, membro_repo: ProjetoMembroRepository, proxima_banca=None
):
    """A forma enxuta, usada nos cards da lista (§6.2)."""
    frentes = frente_repo.get_by_projeto(projeto.id)
    membros = membro_repo.get_by_projeto(projeto.id, apenas_atuais=True)
    coordenador = next((m for m in membros if m.papel == "coordenador"), None)

    return {
        "id": projeto.id,
        "nome": projeto.nome,
        "cliente": projeto.cliente,
        "criado_em": projeto.criado_em,
        "status": projeto.status,
        "frente_ids": [f.frente_id for f in frentes],
        "sinergico": len(frentes) > 1,
        "coordenador_id": coordenador.usuario_id if coordenador else None,
        "consultor_ids": [m.usuario_id for m in membros if m.papel == "consultor"],
        "data_kickoff": projeto.data_kickoff,
        "kickoff_pendente": projeto.data_kickoff is None and projeto.status not in ("finalizado",),
        "arquivado_em": projeto.arquivado_em,
        # "Limpar histórico" (§4): corte de exibição da timeline, não exclusão.
        "historico_oculto_ate": projeto.historico_oculto_ate,
        # §6.2: a banca mais próxima AINDA NÃO REALIZADA de qualquer escopo
        # deste projeto — `None` se nenhuma estiver marcada ou todas já
        # aconteceram.
        "proxima_banca": proxima_banca.data_hora if proxima_banca else None,
    }


def serializar_projeto_completo(
    projeto,
    frente_repo: ProjetoFrenteRepository,
    membro_repo: ProjetoMembroRepository,
    escopos=None,
    fim_ambientacao=None,
):
    """A forma completa, usada na página do projeto (§6.4, aba Visão geral)."""
    resumo = serializar_projeto_resumo(projeto, frente_repo, membro_repo)
    membros = membro_repo.get_by_projeto(projeto.id, apenas_atuais=True)
    return {
        **resumo,
        # 🤖 O último dia de ambientação (§5.3). Vem do backend porque depende
        # de dia útil, e o front não recalcula isso — é ele que a tela usa para
        # avisar quando o projeto vira Em andamento sozinho. `None` = sem
        # janela (sem kickoff ou com zero dias), e aí a saída é manual.
        "fim_ambientacao": fim_ambientacao,
        # Já vêm com a contagem do §5.4 calculada — o front só desenha a barra.
        "escopos": escopos or [],
        "descricao": projeto.descricao,
        "link_proposta": projeto.link_proposta,
        "anexo_proposta_nome": projeto.anexo_proposta_nome,
        "dias_ambientacao": projeto.dias_ambientacao,
        "data_entrega_cliente": projeto.data_entrega_cliente,
        "dia_reuniao_padrao": projeto.dia_reuniao_padrao,
        "criado_por": projeto.criado_por,
        "equipe": [
            {"usuario_id": m.usuario_id, "papel": m.papel, "entrou_em": m.entrou_em}
            for m in membros
        ],
    }


class GetProjetoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.frente_repository = ProjetoFrenteRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(self, projeto_id: int):
        from src.use_cases.projeto_escopo.get_escopos_projeto import ListEscoposProjetoUseCase

        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None
        escopos = ListEscoposProjetoUseCase(self.db).execute(projeto_id)
        return serializar_projeto_completo(
            projeto,
            self.frente_repository,
            self.membro_repository,
            escopos,
            fim_ambientacao=self._fim_ambientacao(projeto),
        )

    def _fim_ambientacao(self, projeto):
        """Mesma régua da faixa do cronograma e da virada automática: dias não
        letivos GLOBAIS, porque a ambientação é do projeto inteiro."""
        if not projeto.data_kickoff or projeto.dias_ambientacao <= 0:
            return None
        limite = projeto.data_kickoff + timedelta(days=365)
        nao_letivos = [
            d.data
            for d in DiaNaoLetivoRepository(self.db).get_por_intervalo(
                projeto.data_kickoff, limite
            )
            if d.frente_id is None
        ]
        return fim_da_ambientacao(projeto.data_kickoff, projeto.dias_ambientacao, nao_letivos)


class ListProjetosUseCase:
    """A lista recortada pela visão (§3) — quem decide o que aparece é o
    `aplicar_recorte_visao`, não esta classe."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.frente_repository = ProjetoFrenteRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, current_user, frente_id: Optional[int] = None, incluir_arquivados: bool = False):
        from src.middlewares.authorization import aplicar_recorte_visao

        query = aplicar_recorte_visao(self.db.query(ProjetoModel), current_user, self.db, frente_id)
        if not incluir_arquivados:
            query = query.filter(ProjetoModel.arquivado_em.is_(None))
        projetos = query.all()

        # §6.2: a banca mais próxima ainda não realizada, por projeto — busca
        # em bloco (escopos de todos os projetos, depois bancas de todos os
        # escopos) pra não virar uma query por card.
        escopos = self.escopo_repository.get_by_projetos([p.id for p in projetos])
        projeto_por_escopo = {e.id: e.projeto_id for e in escopos}
        # Banca ↔ escopo é muitos-para-muitos (uma banca cobre vários escopos)
        # — `mapa_por_escopo` já devolve por escopo, que é a chave que temos.
        banca_por_escopo = self.banca_repository.mapa_por_escopo(list(projeto_por_escopo))
        proxima_por_projeto = {}
        for escopo_id, banca in banca_por_escopo.items():
            if banca.data_hora is None or banca.realizado_em is not None:
                continue
            projeto_id = projeto_por_escopo.get(escopo_id)
            atual = proxima_por_projeto.get(projeto_id)
            if projeto_id and (atual is None or banca.data_hora < atual.data_hora):
                proxima_por_projeto[projeto_id] = banca

        return [
            serializar_projeto_resumo(
                p, self.frente_repository, self.membro_repository, proxima_por_projeto.get(p.id)
            )
            for p in projetos
        ]


class GetHistoricoProjetoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoStatusHistoricoRepository(db)
        self.projeto_repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, incluir_ocultos: bool = False):
        linhas = self.repository.get_by_projeto(projeto_id)
        if not incluir_ocultos:
            projeto = self.projeto_repository.get_by_id(projeto_id)
            corte = projeto.historico_oculto_ate if projeto else None
            if corte:
                linhas = [h for h in linhas if h.alterado_em > corte]
        return [
            {
                "id": h.id,
                "status_anterior": h.status_anterior,
                "status_novo": h.status_novo,
                "alterado_por": h.alterado_por,
                "alterado_em": h.alterado_em,
            }
            for h in linhas
        ]
