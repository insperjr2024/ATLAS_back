"""A senha de primeiro acesso: emitir, enviar e reemitir.

O fluxo inteiro em uma frase: a diretoria cadastra, o sistema sorteia uma
senha, manda por e-mail e marca a conta como `senha_provisoria`; a pessoa
entra com ela e não consegue fazer mais nada até definir a sua (a trava mora
em `middlewares/validate_user_auth_token.py`).

⚠ **A senha em claro só existe no ar**: ela é sorteada, virada em hash e
devolvida UMA vez, na resposta de quem cadastrou. Não é gravada em lugar
nenhum — nem em log, nem em coluna. Quem perder o e-mail não a recupera:
reemite (`ReenviarSenhaProvisoriaUseCase`), que sorteia outra.
"""

import logging

from sqlalchemy.orm import Session

from src.config.config import get_settings
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.email import EmailSender, montar_email_senha_provisoria
from src.utils.exceptions import RegraDeNegocioError
from src.utils.senha import gerar_senha_provisoria, hash_senha

logger = logging.getLogger(__name__)


def emitir_senha_provisoria(usuario_repository, email_sender, usuario) -> tuple[str, bool]:
    """Sorteia a senha, grava o hash, marca a conta e tenta mandar o e-mail.

    Devolve `(senha_em_claro, email_enviado)`.

    ⭐ **Falha de envio NÃO desfaz nada** — e aqui isso é o contrário do que
    `solicitar_recuperacao.py` faz de propósito. Lá o e-mail é o único canal:
    sem ele o token gravado seria lixo que ainda liga o freio de spam. Aqui há
    uma pessoa no meio — a diretoria está na tela, com a senha na resposta, e
    consegue repassá-la por outro canal. Derrubar o cadastro inteiro porque o
    SMTP está fora deixaria o membro sem conta por um motivo que quem está
    cadastrando consegue contornar sozinho.
    """
    senha = gerar_senha_provisoria()
    usuario_repository.update(
        usuario.id, senha_hash=hash_senha(senha), senha_provisoria=True
    )

    settings = get_settings()
    link_login = f"{settings.FRONTEND_URL.rstrip('/')}/login"
    assunto, texto, html = montar_email_senha_provisoria(usuario.nome, senha, link_login)

    try:
        email_sender.enviar(usuario.email_insper, assunto, texto, html)
        return senha, True
    except Exception:
        # `Exception` mesmo, e não só a RegraDeNegocioError do SMTP não
        # configurado: SMTP fora do ar, DNS, timeout e credencial errada
        # chegam aqui como erros de biblioteca, e todos têm a mesma resposta —
        # a conta está criada e a senha está na tela de quem cadastrou.
        logger.warning(
            "Não foi possível enviar a senha provisória para %s", usuario.email_insper,
            exc_info=True,
        )
        return senha, False


class ReenviarSenhaProvisoriaUseCase:
    """Reemitir a senha de primeiro acesso — e-mail perdido, caixa cheia,
    pessoa que trocou de e-mail, ou alguém que simplesmente perdeu o acesso.

    🔒 **Reenviar DERRUBA a senha atual.** Vale inclusive para quem já tinha
    definido a sua: é o caminho da diretoria para devolver acesso a alguém
    trancado para fora. Por isso é ação de diretoria, a mesma régua do
    cadastro — se fosse de qualquer um que gere membros, resetar a senha de um
    diretor viraria escalada de privilégio.
    """

    def __init__(self, db: Session, email_sender=None):
        self.usuario_repository = UsuarioRepository(db)
        self.email_sender = email_sender or EmailSender()

    def execute(self, usuario_id: int):
        usuario = self.usuario_repository.get_by_id(usuario_id)
        if not usuario:
            return None
        # Desativado não volta pelo reenvio — seria contornar o §10, que tira
        # o acesso de quem foi desligado. Mesma trava de `solicitar_recuperacao`.
        if not usuario.ativo:
            raise RegraDeNegocioError(
                "Este membro está desativado — reative a conta antes de reenviar a senha"
            )

        senha, email_enviado = emitir_senha_provisoria(
            self.usuario_repository, self.email_sender, usuario
        )
        return {
            "id": usuario.id,
            "email_insper": usuario.email_insper,
            # Mesmo nome que o cadastro devolve: é a senha EM CLARO, não o
            # booleano `senha_provisoria` que diz "ainda não definiu".
            "senha_provisoria_gerada": senha,
            "email_enviado": email_enviado,
        }
