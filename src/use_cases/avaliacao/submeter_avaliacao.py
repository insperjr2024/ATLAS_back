"""⭐ Submeter a avaliação — e, com o último voto, decidir a banca (§8).

⚠ **Por que uma rota própria, e não o `PATCH /avaliacoes/{id}` de sempre.**
Aquele é um passthrough: joga `request.dict(exclude_unset=True)` direto no
repositório. Pendurar "o voto é obrigatório" ali seria pendurar uma regra de
negócio no lugar onde ela é contornável por qualquer outro campo — bastaria
mandar `{"status": "submetida"}` por outro caminho. Aqui a submissão é uma
AÇÃO, com pré-condições próprias, e é o gancho natural da apuração.
"""

from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.avaliacao_repository import AvaliacaoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.banca_sessao_repository import BancaSessaoRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.use_cases.banca.marcar_banca_escopo import registrar_resultado_na_sessao
from src.utils.apuracao_banca import apurar, eleitorado, votos_por_avaliador
from src.utils.avaliacoes_pendentes import PRAZO_AVALIACAO_DIAS
from src.utils.exceptions import RegraDeNegocioError


class SubmeterAvaliacaoRequest(BaseModel):
    #: ⭐ `True` = aprovo esta banca. Obrigatório: é o voto que decide o
    #: resultado, e uma submissão sem ele não teria como entrar na conta.
    voto_aprovacao: bool
    comentario_feedback: Optional[str] = None


class SubmeterAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AvaliacaoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)

    def execute(self, avaliacao_id: int, request: SubmeterAvaliacaoRequest, usuario_id: int):
        avaliacao = self.repository.get_by_id(avaliacao_id)
        if not avaliacao:
            return None
        if avaliacao.avaliador_id != usuario_id:
            raise RegraDeNegocioError("Você só pode submeter a sua própria avaliação")
        if avaliacao.status == "submetida":
            raise RegraDeNegocioError("Esta avaliação já foi enviada")

        # 🔒 Repetido aqui, e não só na criação: o rascunho pode ser antigo, e
        # é ESTE o ato que conta o voto. Alguém desescalado depois de abrir o
        # formulário não vota na banca de que já não faz parte.
        candidaturas = self.candidatura_repository.get_by_banca(avaliacao.banca_id)
        if not any(c.usuario_id == usuario_id for c in candidaturas):
            raise RegraDeNegocioError(
                "Você não foi escalado para esta banca e não pode avaliá-la"
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

        self.repository.update(
            avaliacao_id,
            status="submetida",
            submetida_em=datetime.now(),
            voto_aprovacao=request.voto_aprovacao,
            comentario_feedback=request.comentario_feedback,
        )

        apuracao = apurar_banca(self.db, banca)
        return {
            "id": avaliacao_id,
            "status": "submetida",
            "voto_aprovacao": request.voto_aprovacao,
            "apuracao": {
                "resultado": apuracao.resultado,
                "aprovacoes": apuracao.aprovacoes,
                "reprovacoes": apuracao.reprovacoes,
                "esperados": apuracao.esperados,
                "motivo": apuracao.motivo,
            },
        }


def apurar_banca(db: Session, banca, prazo_vencido: Optional[bool] = None):
    """Conta os votos da sessão CORRENTE e grava o veredito, se houver.

    ⭐ **Só os votos desta sessão.** `avaliacao.banca_id` é o mesmo nas duas
    tentativas — sem o filtro por `sessao`, os votos que reprovaram a 1ª banca
    reprovariam a 2ª automaticamente, e a segunda chance não existiria.

    Chamada de dois lugares, e é de propósito que a regra viva aqui e não em
    cada um: ao submeter (decide na hora quando o último voto entra) e pelo job
    diário (fecha o que o prazo venceu com quórum parcial).

    Não reapura o que já tem veredito: um resultado gravado — pela maioria ou
    pelo override da diretoria — não é recalculado por um voto atrasado.
    """
    from src.repositories.avaliacao_repository import AvaliacaoRepository
    from src.repositories.candidatura_repository import CandidaturaRepository
    from src.repositories.banca_sessao_repository import BancaSessaoRepository

    if banca.resultado is not None:
        return apurar([], esperados=0, prazo_vencido=True)

    sessao_repository = BancaSessaoRepository(db)
    corrente = sessao_repository.get_corrente(banca.id)
    numero = corrente.numero if corrente else 1

    candidaturas = CandidaturaRepository(db).get_by_banca(banca.id)

    # 🔒 **A urna só conta quem foi ESCALADO.** Esta é a trava que vale, e não
    # as das rotas de escrita.
    #
    # ⚠ Checar só na criação e na submissão deixava um vetor aberto: o
    # `PATCH /avaliacoes/{id}` genérico aceitava trocar o `banca_id` de uma
    # avaliação JÁ submetida, e o voto aterrissava na apuração de outra banca —
    # de um projeto que o votante nem enxerga. Foi assim que um voto de fora
    # fechou uma banca em empate no teste ponta a ponta.
    #
    # Filtrar aqui fecha o vetor por completo, inclusive para caminhos de
    # escrita que ainda não existem: nenhuma rota precisa lembrar da regra para
    # que ela valha.
    escalados = {c.usuario_id for c in candidaturas}
    submetidas = [
        a
        for a in AvaliacaoRepository(db).get_by_banca(banca.id, sessao=numero)
        if a.status == "submetida"
        and a.voto_aprovacao is not None
        # Banca legada, sem candidatura nenhuma, não tem lista de quem esteve
        # lá — filtrar por conjunto vazio zeraria a urna em vez de protegê-la.
        and (not escalados or a.avaliador_id in escalados)
    ]
    avaliacoes = list(votos_por_avaliador(submetidas).values())

    if prazo_vencido is None:
        prazo_vencido = bool(
            banca.realizado_em
            and datetime.now() > banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS)
        )

    apuracao = apurar(
        [a.voto_aprovacao for a in avaliacoes],
        esperados=eleitorado(candidaturas, [a.avaliador_id for a in avaliacoes]),
        prazo_vencido=prazo_vencido,
    )

    if apuracao.resultado is not None:
        atualizada = BancaRepository(db).update(banca.id, resultado=apuracao.resultado)
        registrar_resultado_na_sessao(sessao_repository, atualizada)

    return apuracao
