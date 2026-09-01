import re

from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.senha import verificar_senha
from src.utils.token import criar_access_token
from src.utils.exceptions import RegraDeNegocioError


class LoginRequest(BaseModel):
    email_insper: str
    senha: str


#: Travessões que um cliente de e-mail troca pelo hífen ASCII no
#: "embelezamento" automático: U+2010..U+2015 (hyphen, non-breaking hyphen,
#: figure dash, en dash, em dash, horizontal bar) e U+2212 (sinal de menos).
_TRAVESSOES = re.compile("[‐-―−]")


def _candidatas_senha_provisoria(senha: str) -> list[str]:
    """Formas equivalentes da senha provisória que mudam a APARÊNCIA sem mudar
    o código.

    Ela sai no formato `XXXXX-XXXXX`, vai por e-mail e é lida e digitada (ou
    colada) à mão. No caminho:

    - o cliente de e-mail quebra a linha no meio do código;
    - copiar de um bloco com `letter-spacing` traz espaço entre os caracteres;
    - o "auto-formatar" troca o hífen por um travessão;
    - às vezes o hífen se perde de vez, ou vira espaço.

    O alfabeto da provisória (ver `gerar_senha_provisoria`) é só maiúscula e
    dígito, então `.upper()` também é seguro. Só a provisória passa por aqui:
    a senha própria pode ter espaço ou minúscula de propósito.
    """
    base = _TRAVESSOES.sub("-", "".join(senha.split())).upper()
    candidatas = [base]
    sem_hifen = base.replace("-", "")
    if len(sem_hifen) == 10 and sem_hifen.isalnum():
        candidatas.append(f"{sem_hifen[:5]}-{sem_hifen[5:]}")
    return candidatas


class LoginUseCase:
    def __init__(self, db: Session, usuario_repository=None):
        # Injetável para o teste passar um dublê, mesma costura do
        # `RegistrarUseCase`.
        self.usuario_repository = usuario_repository or UsuarioRepository(db)

    def execute(self, request: LoginRequest):
        # Copiar/colar a credencial costuma trazer um espaço ou quebra de
        # linha junto. Sem isso, e-mail/senha corretos "com espaço sobrando"
        # caem como "Email ou senha incorretos" sem nenhuma pista do porquê.
        email = request.email_insper.strip()
        senha = request.senha.strip()
        usuario = self.usuario_repository.get_by_email_insper(email)
        if not usuario:
            raise RegraDeNegocioError("Email ou senha incorretos")

        senha_confere = verificar_senha(senha, usuario.senha_hash)
        if not senha_confere and usuario.senha_provisoria:
            senha_confere = any(
                c and verificar_senha(c, usuario.senha_hash)
                for c in _candidatas_senha_provisoria(senha)
            )
        if not senha_confere:
            raise RegraDeNegocioError("Email ou senha incorretos")
        if not usuario.ativo:
            raise RegraDeNegocioError("Este usuário está desativado")

        token = criar_access_token(usuario.id)
        return {"access_token": token, "token_type": "bearer"}
