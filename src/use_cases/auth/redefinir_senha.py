"""Passo 2 do "esqueci minha senha": trocar a senha usando o token do e-mail.

Ao contrário do passo 1, **aqui os erros são explícitos**. Não há o que
proteger: quem chegou nesta chamada já tem (ou não) um token válido na mão, e
dizer "esse link expirou" é a única forma da pessoa entender que precisa pedir
outro. O que não se revela é a quem o token pertence.
"""

import hashlib
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.token_recuperacao_repository import TokenRecuperacaoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.senha import TAMANHO_MINIMO_SENHA, hash_senha


class RedefinirSenhaRequest(BaseModel):
    token: str
    nova_senha: str


class RedefinirSenhaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.usuario_repository = UsuarioRepository(db)
        self.token_repository = TokenRecuperacaoRepository(db)

    def execute(self, request: RedefinirSenhaRequest, agora: datetime = None):
        agora = agora or datetime.now()

        if len(request.nova_senha) < TAMANHO_MINIMO_SENHA:
            raise RegraDeNegocioError(
                f"A senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres"
            )

        token_hash = hashlib.sha256(request.token.encode("utf-8")).hexdigest()
        token = self.token_repository.get_por_hash(token_hash)

        # As três recusas usam a MESMA mensagem: token inexistente, já usado e
        # expirado levam à mesma ação do usuário (pedir outro link), e separar
        # as frases só entregaria informação a quem está testando tokens.
        if not token or token.usado_em is not None or token.expira_em <= agora:
            raise RegraDeNegocioError(
                "Este link é inválido ou já expirou. Peça uma nova redefinição."
            )

        usuario = self.usuario_repository.get_by_id(token.usuario_id)
        if not usuario or not usuario.ativo:
            raise RegraDeNegocioError(
                "Este link é inválido ou já expirou. Peça uma nova redefinição."
            )

        # `senha_provisoria=False` junto: quem foi cadastrado e, em vez de
        # entrar com a provisória, caiu no "esqueci minha senha" está definindo
        # a senha dele AGORA. Sem esta linha ele sairia daqui com senha própria
        # e ainda assim preso na tela de definição.
        self.usuario_repository.update(
            usuario.id,
            senha_hash=hash_senha(request.nova_senha),
            senha_provisoria=False,
        )
        # Fecha o token DEPOIS de trocar a senha: se a troca falhar, o link
        # continua valendo e a pessoa pode tentar de novo.
        self.token_repository.marcar_usado(token, agora)

        return {"mensagem": "Senha redefinida. Faça login com a nova senha."}
