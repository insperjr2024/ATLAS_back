"""§7.4 — o "porquê" do atraso, digitado pela diretoria.

O alerta de atraso é automático (`src/utils/atraso_monitoramento.py`): o
projeto fica vermelho no monitoramento sem ninguém digitar nada. Esta é a
outra metade da regra — a diretoria pergunta ao coordenador e registra a
nota, que fica gravada no histórico do projeto (`GetHistoricoProjetoUseCase`)
pra sempre. Não é um campo que se edita: cada chamada cria uma nota nova.
"""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_justificativa_atraso_repository import (
    ProjetoJustificativaAtrasoRepository,
)
from src.repositories.projeto_repository import ProjetoRepository
from src.utils.exceptions import RegraDeNegocioError


MOTIVOS_VALIDOS = {"banca", "entrega_interna", "entrega_externa"}


class RegistrarJustificativaAtrasoRequest(BaseModel):
    texto: str
    #: Qual escopo esta nota explica — opcional; None quando a diretoria está
    #: falando do atraso do projeto como um todo, não de um escopo isolado.
    projeto_escopo_id: Optional[int] = None
    #: "banca" | "entrega_interna" | "entrega_externa" — o MESMO escopo pode
    #: estar atrasado em banca e entrega ao mesmo tempo (ex: Projeto Beta),
    #: então só o escopo não basta pra dizer qual dos dois foi respondido.
    motivo_tipo: Optional[str] = None


class RegistrarJustificativaAtrasoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoJustificativaAtrasoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, projeto_id: int, request: RegistrarJustificativaAtrasoRequest, registrado_por: int):
        if not self.projeto_repository.get_by_id(projeto_id):
            return None

        texto = (request.texto or "").strip()
        if not texto:
            raise RegraDeNegocioError("A justificativa não pode ficar vazia")

        if request.motivo_tipo is not None and request.motivo_tipo not in MOTIVOS_VALIDOS:
            raise RegraDeNegocioError(f"Tipo de motivo inválido: {request.motivo_tipo}")

        if request.projeto_escopo_id is not None:
            escopo = self.escopo_repository.get_by_id(request.projeto_escopo_id)
            if not escopo or escopo.projeto_id != projeto_id:
                raise RegraDeNegocioError("Esse escopo não pertence a este projeto")

        justificativa = self.repository.create(
            projeto_id=projeto_id,
            projeto_escopo_id=request.projeto_escopo_id,
            tipo=request.motivo_tipo,
            texto=texto,
            registrado_por=registrado_por,
        )
        return {
            "tipo": "justificativa_atraso",
            "id": justificativa.id,
            "projeto_id": justificativa.projeto_id,
            "projeto_escopo_id": justificativa.projeto_escopo_id,
            "motivo_tipo": justificativa.tipo,
            "texto": justificativa.texto,
            "registrado_por": justificativa.registrado_por,
            "alterado_em": justificativa.registrado_em,
        }
