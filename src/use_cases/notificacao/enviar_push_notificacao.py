"""O evento do sino também vai por push (Web Push), pros aparelhos que a
pessoa ativou. Mesmo desenho de `enviar_email_notificacao.py`, pelos mesmos
motivos:

- **Fora da thread da request, falhando calado.** Notificar nunca derruba a
  ação que gerou o evento; o sino continua sendo o canal principal.
- **Nunca com conexão de banco na mão durante o envio.** Lê inscrições e
  preferências numa sessão, fecha, chama o serviço de push e só então abre
  outra pra limpar inscrição morta e carimbar o envio.

**Quem recebe.** Só quem ativou num aparelho (a inscrição é opt-in, por
aparelho). Respeita os tipos que a pessoa desligou em "Notificações por
e-mail" no Meu Perfil: quem não quer um aviso por e-mail também não quer no
celular. O desligamento total (`EMAIL_DESATIVADO_TOTAL`) NÃO vale aqui: ele
existe pra conta de teste com e-mail que não existe, e push só chega em
aparelho que alguém ativou de propósito.

**Inscrição morta.** O serviço de push responde 404/410 quando o navegador
descartou a inscrição (app removido, permissão revogada). Aí a linha é
apagada; tentar de novo seria inútil.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Optional

from src.config.config import get_settings
from src.database.database import SessionLocal
from src.models.notificacao_model import TIPOS_NOTIFICACAO_OPCIONAIS
from src.repositories.push_inscricao_repository import PushInscricaoRepository
from src.repositories.usuario_repository import UsuarioRepository

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="push-notificacao")

#: Quanto tempo o serviço de push guarda a mensagem se o aparelho estiver
#: desligado. Um dia: aviso de ontem que chega hoje ainda serve; de semana
#: passada, não.
TTL_SEGUNDOS = 24 * 60 * 60

#: O texto aparece numa notificação do sistema, que corta cedo.
CORPO_MAX = 300


def push_configurado() -> bool:
    settings = get_settings()
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def enfileirar_push(*, usuario_id: int, tipo: str, titulo: str, corpo: Optional[str], rota: Optional[str]) -> None:
    """Devolve na hora; o envio acontece numa thread do pool. Recebe valores
    soltos, nunca objeto de sessão (mesmo motivo do e-mail)."""
    if not push_configurado():
        return
    try:
        _executor.submit(enviar_push, usuario_id=usuario_id, tipo=tipo, titulo=titulo, corpo=corpo, rota=rota)
    except RuntimeError:
        logger.warning("Push do usuário %s não enfileirado: app encerrando", usuario_id)


def _webpush_padrao(**kwargs):
    from pywebpush import webpush

    return webpush(**kwargs)


def enviar_push(
    *,
    usuario_id: int,
    tipo: str,
    titulo: str,
    corpo: Optional[str],
    rota: Optional[str],
    webpush_fn: Callable = _webpush_padrao,
    session_factory=SessionLocal,
) -> int:
    """Manda pra cada aparelho da pessoa. Devolve quantos aceitaram.

    `webpush_fn` e `session_factory` são injetáveis pro teste não falar com
    serviço de push de verdade."""
    if not push_configurado():
        return 0
    try:
        inscricoes = _inscricoes_do_destinatario(usuario_id, tipo, session_factory)
        if not inscricoes:
            return 0

        settings = get_settings()
        dados = json.dumps(
            {
                "titulo": titulo,
                "corpo": (corpo or "")[:CORPO_MAX],
                "url": "/" + (rota or "notificacoes").lstrip("/"),
                "tipo": tipo,
            },
            ensure_ascii=False,
        )
        assunto = settings.VAPID_SUBJECT or f"mailto:{settings.SMTP_USER}"

        entregues, mortas = [], []
        for inscricao_id, endpoint, p256dh, auth in inscricoes:
            try:
                webpush_fn(
                    subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                    data=dados,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": assunto},
                    ttl=TTL_SEGUNDOS,
                )
                entregues.append(inscricao_id)
            except Exception as erro:  # noqa: BLE001 (ver a docstring do módulo)
                status = getattr(getattr(erro, "response", None), "status_code", None)
                if status in (404, 410):
                    mortas.append(endpoint)
                else:
                    logger.warning("Push recusado (%s) pro usuário %s: %s", status, usuario_id, erro)

        _limpar_e_carimbar(entregues, mortas, session_factory)
        return len(entregues)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao enviar push pro usuário %s", usuario_id)
        return 0


def _inscricoes_do_destinatario(usuario_id: int, tipo: str, session_factory) -> list[tuple]:
    """`[(id, endpoint, p256dh, auth)]`, vazio quando não deve receber.
    Devolve valores, não objetos: a sessão fecha antes do envio."""
    db = session_factory()
    try:
        usuario = UsuarioRepository(db).get_by_id(usuario_id)
        if usuario is None or not usuario.ativo:
            return []
        desativadas = usuario.notificacoes_email_desativadas or []
        if tipo in TIPOS_NOTIFICACAO_OPCIONAIS and tipo in desativadas:
            return []
        return [(i.id, i.endpoint, i.p256dh, i.auth) for i in PushInscricaoRepository(db).get_by_usuario(usuario_id)]
    finally:
        db.close()


def _limpar_e_carimbar(entregues: list[int], mortas: list[str], session_factory) -> None:
    if not entregues and not mortas:
        return
    db = session_factory()
    try:
        repo = PushInscricaoRepository(db)
        for endpoint in mortas:
            repo.remover_por_endpoint(endpoint)
        repo.marcar_envio(entregues, datetime.now())
    finally:
        db.close()
