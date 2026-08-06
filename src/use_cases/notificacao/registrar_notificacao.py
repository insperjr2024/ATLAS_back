"""O gancho que os outros use cases chamam para gravar um 📌 evento.

Um evento aconteceu num instante e não é recalculável depois — ninguém sabe
quando você entrou no Projeto Alfa se a linha não for gravada ali. É a metade
do §6.6 que precisa de escrita; a outra (as 🔄 condições) é derivada na
leitura por `condicoes_alerta`.

⚠ **Notificar nunca pode derrubar a ação que a gerou.** Se o registro falhar,
alocar alguém numa equipe tem que continuar funcionando: o aviso é um efeito
colateral do trabalho, não o trabalho. Por isso `registrar` engole a exceção e
segue — a decisão oposta à de `solicitar_recuperacao`, onde o e-mail É o
fluxo e falhar calado deixaria a pessoa esperando um link que nunca chega.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.notificacao_repository import NotificacaoRepository

logger = logging.getLogger(__name__)


def registrar(
    db: Session,
    *,
    usuario_id: int,
    tipo: str,
    titulo: str,
    chave_dedup: str,
    projeto_id: Optional[int] = None,
    corpo: Optional[str] = None,
    rota: Optional[str] = None,
    payload: Optional[dict] = None,
) -> None:
    """Grava o evento para UMA pessoa. Silenciosamente no-op se já existir."""
    dados = dict(payload or {})
    if rota:
        # A rota viaja no payload em vez de virar coluna: só o evento a usa, e
        # a condição já a calcula em `condicoes_alerta`.
        dados["rota"] = rota
    try:
        NotificacaoRepository(db).criar_se_nao_existe(
            usuario_id=usuario_id,
            tipo=tipo,
            origem="evento",
            titulo=titulo,
            corpo=corpo,
            projeto_id=projeto_id,
            payload=dados or None,
            chave_dedup=chave_dedup,
        )
    except Exception:  # noqa: BLE001 — ver a docstring do módulo
        logger.exception("Falha ao registrar notificação %s para o usuário %s", tipo, usuario_id)


def registrar_varios(db: Session, usuario_ids, **kwargs) -> None:
    """Mesmo evento para várias pessoas — a chave é a mesma, o destinatário não.

    Duplicatas na lista são normais (a mesma pessoa em dois papéis) e o
    `criar_se_nao_existe` já as absorve.
    """
    for usuario_id in dict.fromkeys(usuario_ids):
        registrar(db, usuario_id=usuario_id, **kwargs)
