"""O primeiro acesso: trocar a senha provisória pela própria.

Irmão de `redefinir_senha.py`, com uma diferença que muda tudo: **lá o segredo
é o token do e-mail, aqui é a sessão**. Quem chama isto já está logado (entrou
com a provisória), então não há token de uso único para conferir — a
autenticação já provou quem é.

É o único endpoint, junto de `/auth/me` e `/auth/renovar`, que responde
enquanto a conta está com senha provisória. Sem essa exceção, a pessoa entra e
não tem como sair do estado — a trava travaria a própria saída.
"""

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.senha import TAMANHO_MINIMO_SENHA, hash_senha, verificar_senha


class DefinirSenhaRequest(BaseModel):
    nova_senha: str


class DefinirSenhaUseCase:
    def __init__(self, db: Session):
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, usuario, request: DefinirSenhaRequest):
        if len(request.nova_senha) < TAMANHO_MINIMO_SENHA:
            raise RegraDeNegocioError(
                f"A senha precisa ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres"
            )

        # Repetir a provisória seria sair da tela sem sair do problema: a senha
        # que veio por e-mail continuaria valendo, e ela passou por uma caixa
        # de entrada — que é justamente o que este fluxo existe para encerrar.
        if verificar_senha(request.nova_senha, usuario.senha_hash):
            raise RegraDeNegocioError(
                "A nova senha precisa ser diferente da que você recebeu por e-mail"
            )

        self.usuario_repository.update(
            usuario.id,
            senha_hash=hash_senha(request.nova_senha),
            # ⭐ É esta linha que destrava a plataforma: `get_current_user`
            # para de recusar as outras rotas assim que ela cai.
            senha_provisoria=False,
        )
        return {"mensagem": "Senha definida. Bem-vindo ao ATLAS."}
