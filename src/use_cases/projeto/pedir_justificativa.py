"""§7.4: a diretoria pergunta ao coordenador por que o escopo atrasou."""

import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.justificativa_pedido_repository import JustificativaPedidoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.use_cases.notificacao.eventos import notificar_justificativa_pedida
from src.utils.exceptions import RegraDeNegocioError

logger = logging.getLogger(__name__)


class PedirJustificativaRequest(BaseModel):
    #: Qual motivo está sendo cobrado. Nulo = o projeto como um todo.
    projeto_escopo_id: Optional[int] = None
    tipo: Optional[str] = None
    #: O que aparece no aviso do coordenador ("banca de Análise venceu há 16
    #: dias"). Vem pronto de quem pede, que é quem tem a frase na tela.
    sobre: Optional[str] = None


class PedirJustificativaUseCase:
    """⭐ Torna explícito o passo que o §7.4 descreve e a plataforma não tinha.

    O case diz: "a justificativa é registrada pela diretoria: **ela pergunta ao
    coordenador** e digita a nota". Só a segunda metade existia — a caixa de
    texto. A pergunta acontecia por fora, e nada registrava quem perguntou,
    quando, nem se já haviam respondido. A diretora reabria a fila na semana
    seguinte sem saber se aquele atraso já tinha sido cobrado.

    ⚠ **Não substitui a nota direta.** Quem já sabe o porquê continua
    escrevendo na hora; pedir é o caminho de quem NÃO sabe.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = JustificativaPedidoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(self, projeto_id: int, request: PedirJustificativaRequest, current_user):
        projeto = self.projeto_repository.get_by_id(projeto_id)
        if not projeto:
            return None

        # ⚠ Dedup por MOTIVO: clicar duas vezes não gera dois pedidos nem dois
        # avisos para a mesma pergunta.
        aberto = self.repository.get_aberto_do_motivo(
            projeto_id, request.projeto_escopo_id, request.tipo
        )
        if aberto:
            raise RegraDeNegocioError(
                "Já existe um pedido de explicação em aberto para este motivo"
            )

        coordenador = self._coordenador(projeto_id)
        if not coordenador:
            raise RegraDeNegocioError(
                "Este projeto está sem coordenador — não há a quem perguntar"
            )

        pedido = self.repository.create(
            projeto_id=projeto_id,
            projeto_escopo_id=request.projeto_escopo_id,
            tipo=request.tipo,
            solicitado_por=getattr(current_user, "id", None),
            solicitado_em=datetime.now(),
        )

        try:
            notificar_justificativa_pedida(
                self.db,
                projeto,
                coordenador,
                request.sobre or "A diretoria pediu o porquê do atraso.",
                pedido.id,
            )
        except Exception:  # noqa: BLE001
            # O pedido vale mesmo sem o aviso: ele aparece na tela do projeto.
            logger.exception("Pedido %s criado, mas o aviso não saiu", pedido.id)

        return {
            "id": pedido.id,
            "projeto_id": projeto_id,
            "projeto_escopo_id": pedido.projeto_escopo_id,
            "tipo": pedido.tipo,
            "solicitado_em": pedido.solicitado_em,
            "coordenador_id": coordenador,
        }

    def _coordenador(self, projeto_id: int) -> Optional[int]:
        membros = self.membro_repository.get_by_projeto(projeto_id, apenas_atuais=True)
        for m in membros:
            if m.papel == "coordenador":
                return m.usuario_id
        return None


def fechar_pedidos_cobertos(db: Session, projeto_id: int, justificativa) -> int:
    """Fecha os pedidos que a nota recém-escrita responde.

    ⭐ **Fecha sozinho, e é o que faz o ciclo se sustentar.** Um pedido que só
    fecha por alguém clicar "resolvido" fica aberto para sempre — e a fila da
    diretoria volta a mentir, agora com pedidos fantasma.

    A régua é a de `justificativa_cobrindo`, de trás para frente: a nota cobre
    o pedido quando é mais ampla ou igual a ele. Nota geral do projeto (sem
    escopo) fecha qualquer pedido; nota de um escopo fecha os pedidos daquele
    escopo; nota com tipo fecha só os do mesmo tipo.
    """
    repo = JustificativaPedidoRepository(db)
    fechados = 0
    for pedido in repo.get_abertos_do_projeto(projeto_id):
        if justificativa.projeto_escopo_id is not None and (
            pedido.projeto_escopo_id != justificativa.projeto_escopo_id
        ):
            continue
        if justificativa.tipo is not None and pedido.tipo not in (None, justificativa.tipo):
            continue
        repo.update(
            pedido.id, respondido_em=datetime.now(), justificativa_id=justificativa.id
        )
        fechados += 1
    return fechados
