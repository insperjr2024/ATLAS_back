from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.senha import verificar_senha
from src.utils.token import criar_access_token
from src.utils.exceptions import RegraDeNegocioError


class LoginRequest(BaseModel):
    email_insper: str
    senha: str


class LoginUseCase:
    def __init__(self, db: Session):
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, request: LoginRequest):
        usuario = self.usuario_repository.get_by_email_insper(request.email_insper)
        if not usuario or not verificar_senha(request.senha, usuario.senha_hash):
            raise RegraDeNegocioError("Email ou senha incorretos")
        if not usuario.ativo:
            raise RegraDeNegocioError("Este usuário está desativado")

        token = criar_access_token(usuario.id)
        return {"access_token": token, "token_type": "bearer"}