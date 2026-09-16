"""Repescagem de e-mail de notificação perdido (2026-09-16, incidente real).

O envio de e-mail acontece numa thread em background
(`enviar_email_notificacao.enfileirar`), DENTRO do processo que atendeu a
request — não numa fila externa. Se o processo reinicia (deploy, restart)
enquanto ainda há e-mails do mesmo lote na fila de threads, essas tarefas
morrem junto: sem exceção, sem log, sem nova tentativa. `email_enviado_em`
fica nulo pra sempre nesse caso — e é indistinguível, só pela coluna, de
"nunca foi tentado" ou "SMTP recusou".

Foi assim que a remarcação da banca ANTIQUÁRIO I avisou por e-mail 10 de 11
inscritos: o 11º ficou na fila quando o processo caiu (deploy do backend em
cima da hora) e nunca chegou a bater na API do Resend — o aviso continuou no
sino normalmente, só o e-mail se perdeu, sem reenvio automático nenhum.

Este job cobre exatamente essa lacuna: de tempos em tempos, reenfileira quem
ficou pendente numa janela recente.
"""

from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from src.repositories.notificacao_repository import NotificacaoRepository
from src.use_cases.notificacao.enviar_email_notificacao import enfileirar as _enfileirar_padrao

#: Não existe "reenviar pra sempre" — passado isso, cobrir a lacuna vira
#: decisão manual de quem viu o problema (como este mesmo incidente: o
#: reenvio do e-mail perdido foi feito à mão, por fora deste job).
JANELA_PADRAO = timedelta(hours=2)


def reenviar_emails_pendentes(
    db: Session,
    *,
    janela: timedelta = JANELA_PADRAO,
    agora: Optional[datetime] = None,
    enfileirar_fn: Callable = _enfileirar_padrao,
) -> int:
    """Reenfileira quem está pendente; devolve quantos.

    `enfileirar_fn` é injetável pelo mesmo motivo de `enviar()` em
    `enviar_email_notificacao.py`: o teste passa um espião e não dispara
    thread nem e-mail de verdade.
    """
    desde = (agora or datetime.now()) - janela
    pendentes = NotificacaoRepository(db).get_pendentes_de_email(desde=desde)
    for linha in pendentes:
        enfileirar_fn(
            notificacao_id=linha.id,
            usuario_id=linha.usuario_id,
            tipo=linha.tipo,
            titulo=linha.titulo,
            corpo=linha.corpo,
            rota=(linha.payload or {}).get("rota"),
        )
    return len(pendentes)
