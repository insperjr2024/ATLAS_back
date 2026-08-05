from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func
from src.database.database import Base


class TokenRecuperacaoModel(Base):
    """O token de uso único que vai no link de "esqueci minha senha".

    **Nunca guarda o token cru.** A coluna é o sha256 dele: se o banco vazar,
    o que está aqui não redefine a senha de ninguém. É o mesmo princípio do
    `senha_hash` em `usuario`.

    sha256 e não bcrypt (que o `utils/senha.py` usa) porque o problema é
    outro. bcrypt é lento de propósito e salga cada hash — isso protege senha
    humana, que é fraca e adivinhável. Aqui o segredo é
    `secrets.token_urlsafe(32)`, inadivinhável de qualquer jeito, então a
    lentidão não compra nada; e o salt impediria buscar por
    `WHERE token_hash = ?`, obrigando a varrer a tabela inteira a cada
    tentativa. sha256 é determinístico e a busca sai pelo índice.

    **Por que tabela e não um JWT assinado**, já que o projeto tem o
    `python-jose`:

    1. JWT não é revogável. O link continuaria funcionando até expirar, mesmo
       depois de usado — e e-mail é coisa que fica (encaminhado, computador
       compartilhado, histórico). Aqui `usado_em` fecha na primeira vez.
    2. `utils/token.py::decodificar_access_token` aceita QUALQUER JWT assinado
       com a `SECRET_KEY` e só lê o `sub`, sem checar para que o token serve.
       Um JWT de reset seria aceito como `Authorization: Bearer` — o link de
       redefinir senha viraria um link de login.
    """

    __tablename__ = "token_recuperacao"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    #: sha256 em hexadecimal — 64 caracteres, tamanho fixo.
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expira_em = Column(DateTime, nullable=False)
    #: Preenchido no primeiro uso. É o que torna o token de uso único.
    usado_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
