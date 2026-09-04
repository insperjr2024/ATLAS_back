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

from src.repositories.avaliacao_repository import AvaliacaoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
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
