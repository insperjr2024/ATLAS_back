"""Submeter a avaliação — o formulário de notas e feedback pedagógico (§8).

⚠ **Por que uma rota própria, e não o `PATCH /avaliacoes/{id}` de sempre.**
Aquele é um passthrough: joga `request.dict(exclude_unset=True)` direto no
repositório. Pendurar as pré-condições de envio (banca realizada, dentro do
prazo, não reenviar) ali seria pendurar regra de negócio no lugar onde ela é
contornável por qualquer outro campo. Aqui a submissão é uma AÇÃO própria.

⚠ **Não decide mais a banca.** Quem aprova ou reprova é diretoria de projetos
+ gerente da frente (`use_cases/banca/aprovar_banca.py`), não a maioria dos
avaliadores — esta submissão só fecha o formulário de notas e comentário.
"""

from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository
from src.repositories.avaliacao_repository import AvaliacaoRepository
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.use_cases.formulario.get_formulario_ativo import GetFormularioAtivoUseCase
from src.utils.avaliacoes_pendentes import PRAZO_AVALIACAO_DIAS
from src.utils.exceptions import RegraDeNegocioError


class SubmeterAvaliacaoRequest(BaseModel):
    comentario_feedback: Optional[str] = None


class SubmeterAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AvaliacaoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.nota_repository = AvaliacaoNotaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.projeto_escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, avaliacao_id: int, request: SubmeterAvaliacaoRequest, usuario_id: int):
        avaliacao = self.repository.get_by_id(avaliacao_id)
        if not avaliacao:
            return None
        if avaliacao.avaliador_id != usuario_id:
            raise RegraDeNegocioError("Você só pode submeter a sua própria avaliação")
        if avaliacao.status == "submetida":
            raise RegraDeNegocioError("Esta avaliação já foi enviada")

        # 🔒 Repetido aqui, e não só na criação: o rascunho pode ser antigo, e
        # é ESTE o ato que fecha a avaliação. Alguém desescalado depois de
        # abrir o formulário não avalia a banca de que já não faz parte.
        candidaturas = self.candidatura_repository.get_by_banca(avaliacao.banca_id)
        if not any(c.usuario_id == usuario_id for c in candidaturas):
            raise RegraDeNegocioError(
                "Você não foi escalado para esta banca e não pode avaliá-la"
            )

        # 🔒 Repetido aqui pela mesma razão da checagem acima: `create_avaliacao`
        # recusa abrir um formulário novo depois do envio, mas um RASCUNHO
        # criado ANTES dele já existia e continuaria submissível.
        outra_submetida = any(
            a.id != avaliacao.id
            and a.avaliador_id == usuario_id
            and a.status == "submetida"
            for a in self.repository.get_by_banca(avaliacao.banca_id, sessao=avaliacao.sessao)
        )
        if outra_submetida:
            raise RegraDeNegocioError(
                "Você já enviou sua avaliação desta banca — não pode ser refeita"
            )

        banca = self.banca_repository.get_by_id(avaliacao.banca_id)
        if not banca or not banca.realizado_em:
            raise RegraDeNegocioError(
                "Esta banca ainda não foi registrada como realizada"
            )
        if datetime.now() > banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS):
            raise RegraDeNegocioError(
                f"O prazo de {PRAZO_AVALIACAO_DIAS} dias para avaliar esta banca já passou"
            )

        self._exigir_criterios_completos(avaliacao_id, banca)

        self.repository.update(
            avaliacao_id,
            status="submetida",
            submetida_em=datetime.now(),
            comentario_feedback=request.comentario_feedback,
        )

        return {
            "id": avaliacao_id,
            "status": "submetida",
            "comentario_feedback": request.comentario_feedback,
        }

    def _exigir_criterios_completos(self, avaliacao_id: int, banca) -> None:
        """⭐ Tudo-ou-nada nos critérios (2026-09-10, a pedido). Quem respondeu
        ALGUM critério tem que responder todos os do formulário ATIVO, pros
        escopos que a banca cobre.

        Existe porque o formulário é carregado uma vez no front: se a diretoria
        adiciona critérios de um escopo enquanto a pessoa está com a tela
        aberta, aquele bloco aparece como "sem critérios" e a avaliação ia
        incompleta — foi o que aconteceu na BLEND I (Enzo pulou Pesquisa
        Legislativa inteira, Valentina pulou Análise Mercadológica).

        Zero critérios (comentário puro, o atalho da aba Banca do projeto)
        continua valendo — não é submissão do formulário completo.
        """
        # Import local: `get_banca` puxa meia dúzia de use cases, e no topo
        # fecharia um ciclo com este módulo.
        from src.use_cases.banca.get_banca import escopos_avaliados_ids

        respondidas = {n.pergunta_id for n in self.nota_repository.get_by_avaliacao(avaliacao_id)}
        if not respondidas:
            return

        form = GetFormularioAtivoUseCase(self.db).execute()
        if not form:
            return

        pe_ids = self.banca_escopo_repository.get_escopo_ids(banca.id)
        pe_por_id = {pe.id: pe for pe in self.projeto_escopo_repository.get_by_ids(pe_ids)}
        cobertos = set(escopos_avaliados_ids(pe_ids, pe_por_id, banca.escopo_id))

        obrigatorias = {
            p["id"]
            for p in form["perguntas"]
            if p["tipo_resposta"] == "nota"
            and (p["escopo_id"] is None or p["escopo_id"] in cobertos)
        }
        if obrigatorias - respondidas:
            raise RegraDeNegocioError(
                "O formulário tem critérios que você não respondeu — provavelmente "
                "ele foi atualizado enquanto você preenchia. Recarregue a página e "
                "responda os critérios que faltam antes de enviar."
            )
