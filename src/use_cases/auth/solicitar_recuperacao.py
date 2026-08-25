"""Passo 1 do "esqueci minha senha": gerar o token e mandar o e-mail.

A decisão que manda neste arquivo: **a resposta é sempre a mesma**, exista o
e-mail ou não. Responder "e-mail não encontrado" transformaria o endpoint num
verificador de quem é membro do núcleo — qualquer pessoa descobriria a lista
inteira testando endereços. Quem não existe simplesmente não recebe nada.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.config.config import get_settings
from src.repositories.token_recuperacao_repository import TokenRecuperacaoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.email import EmailSender, montar_email_recuperacao

#: A mesma frase para todos os casos — ver docstring do módulo.
RESPOSTA_NEUTRA = {
    "mensagem": "Se este e-mail estiver cadastrado, enviamos o link de redefinição."
}


def hash_token(token: str) -> str:
    """sha256 em hexadecimal. O banco nunca vê o token cru."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SolicitarRecuperacaoRequest(BaseModel):
    email_insper: str


class SolicitarRecuperacaoUseCase:
    def __init__(self, db: Session, email_sender=None):
        self.db = db
        self.usuario_repository = UsuarioRepository(db)
        self.token_repository = TokenRecuperacaoRepository(db)
        # Injetável para o teste passar um dublê. Sem isso, rodar a suíte
        # mandaria e-mail de verdade.
        self.email_sender = email_sender or EmailSender()

    def execute(self, request: SolicitarRecuperacaoRequest, agora: datetime = None):
        agora = agora or datetime.now()
        settings = get_settings()

        # .strip() pelo mesmo motivo do login: e-mail colado do Gmail ou
        # preenchido pelo teclado do celular costuma trazer espaço sobrando.
        # Sem isso a busca falha, a pessoa cai na resposta neutra e nunca
        # descobre que o problema foi um espaço, porque essa resposta não
        # revela se o usuário foi encontrado ou não.
        email = request.email_insper.strip()
        usuario = self.usuario_repository.get_by_email_insper(email)

        # Usuário inexistente ou desativado: sai calado, com a resposta neutra.
        # Desativado não pode voltar pelo reset — seria contornar o §10, que
        # tira o acesso de quem foi desligado.
        if not usuario or not usuario.ativo:
            return RESPOSTA_NEUTRA

        # Freio de spam. Sem ele, um terceiro enche a caixa de qualquer membro
        # repetindo a chamada. Também responde neutro: dizer "espere 2 minutos"
        # confirmaria que o e-mail existe.
        ultimo = self.token_repository.get_ultimo_do_usuario(usuario.id)
        if ultimo and ultimo.criado_em:
            desde_o_ultimo = (agora - ultimo.criado_em).total_seconds()
            if desde_o_ultimo < settings.RESET_INTERVALO_MINIMO_SEGUNDOS:
                return RESPOSTA_NEUTRA

        token = secrets.token_urlsafe(32)
        link = f"{settings.FRONTEND_URL.rstrip('/')}/redefinir-senha?token={token}"
        assunto, texto, html = montar_email_recuperacao(
            usuario.nome, link, settings.RESET_TOKEN_EXPIRE_MINUTES
        )

        # ⚠ O envio vem ANTES de qualquer escrita no banco, e a ordem importa.
        #
        # Fazendo o contrário, um envio que falha (SMTP fora do ar, credencial
        # errada) deixa para trás um token órfão — que ainda por cima liga o
        # freio de spam e impede a pessoa de tentar de novo pelos próximos
        # minutos. Ou seja: ela toma erro E fica bloqueada.
        #
        # Nesta ordem, envio que falha não deixa rastro nenhum: nada gravado,
        # nada invalidado, e a nova tentativa é imediata.
        self.email_sender.enviar(usuario.email_insper, assunto, texto, html)

        # Só agora, com o e-mail já a caminho: derruba os links anteriores —
        # dois válidos ao mesmo tempo significa que o mais antigo, o que teve
        # mais tempo exposto na caixa, continua servindo.
        self.token_repository.invalidar_pendentes(usuario.id, agora)
        self.token_repository.create(
            usuario_id=usuario.id,
            token_hash=hash_token(token),
            # criado_em explícito, e não o server_default da coluna: aquele é
            # func.now() do Postgres, que no Supabase é UTC, enquanto todo o
            # resto do sistema grava carimbo de auditoria com datetime.now()
            # (hora local, ver src/utils/fuso.py). Sem isso o freio de spam
            # logo abaixo compara "agora" local com um criado_em em UTC, a
            # subtração dá negativa, e o freio trava a próxima solicitação
            # de verdade por até 3 horas sem avisar ninguém.
            criado_em=agora,
            expira_em=agora + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        )

        return RESPOSTA_NEUTRA
