from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.models.projeto_model import ProjetoModel
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_justificativa_atraso_repository import (
    ProjetoJustificativaAtrasoRepository,
)
from src.repositories.projeto_remarcacao_banca_repository import ProjetoRemarcacaoBancaRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.utils.ambientacao import fim_da_ambientacao


def serializar_projeto_resumo(projeto, frente_repo: ProjetoFrenteRepository, membro_repo: ProjetoMembroRepository):
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

    def execute(self, current_user, frente_id: Optional[int] = None, incluir_arquivados: bool = False):
        from src.middlewares.authorization import aplicar_recorte_visao

        query = aplicar_recorte_visao(self.db.query(ProjetoModel), current_user, self.db, frente_id)
        if not incluir_arquivados:
            query = query.filter(ProjetoModel.arquivado_em.is_(None))
        projetos = query.all()
        return [
            serializar_projeto_resumo(p, self.frente_repository, self.membro_repository)
            for p in projetos
        ]


class GetHistoricoProjetoUseCase:
    """A linha do tempo do projeto — status (F4), justificativa de atraso
    (§7.4) e remarcação de banca (§5.6) juntos, ordenados por data. Reajustes
    de cronograma entram aqui na F11, na mesma lista."""

    def __init__(self, db: Session):
        self.repository = ProjetoStatusHistoricoRepository(db)
        self.justificativa_repository = ProjetoJustificativaAtrasoRepository(db)
        self.remarcacao_repository = ProjetoRemarcacaoBancaRepository(db)

    def execute(self, projeto_id: int):
        status = [
            {
                "tipo": "status",
                "id": h.id,
                "status_anterior": h.status_anterior,
                "status_novo": h.status_novo,
                "alterado_por": h.alterado_por,
                "alterado_em": h.alterado_em,
            }
            for h in self.repository.get_by_projeto(projeto_id)
        ]
        justificativas = [
            {
                "tipo": "justificativa_atraso",
                "id": j.id,
                "projeto_escopo_id": j.projeto_escopo_id,
                "motivo_tipo": j.tipo,
                "texto": j.texto,
                "registrado_por": j.registrado_por,
                "alterado_em": j.registrado_em,
            }
            for j in self.justificativa_repository.get_by_projeto(projeto_id)
        ]
        remarcacoes = [
            {
                "tipo": "remarcacao_banca",
                "id": r.id,
                "projeto_escopo_id": r.projeto_escopo_id,
                "data_anterior": r.data_anterior,
                "data_nova": r.data_nova,
                "justificativa": r.justificativa,
                "registrado_por": r.registrado_por,
                "alterado_em": r.registrado_em,
            }
            for r in self.remarcacao_repository.get_by_projeto(projeto_id)
        ]
        return sorted(status + justificativas + remarcacoes, key=lambda h: h["alterado_em"])
