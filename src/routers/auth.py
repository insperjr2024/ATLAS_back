from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import require_diretor
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.auth.login import LoginUseCase, LoginRequest
from src.use_cases.auth.redefinir_senha import RedefinirSenhaUseCase, RedefinirSenhaRequest
from src.use_cases.auth.registrar import RegistrarUseCase, RegistrarRequest
from src.use_cases.auth.solicitar_recuperacao import (
    SolicitarRecuperacaoUseCase,
    SolicitarRecuperacaoRequest,
)
from src.utils.exceptions import RegraDeNegocioError
from src.utils.token import criar_access_token

# Rotas sem token: login e a recuperação de senha. O registro fica no router
# protegido abaixo — o §10 do briefing é explícito em que ninguém se
# auto-registra. A recuperação PRECISA ser pública: quem esqueceu a senha não
# tem como se autenticar para pedir a troca.
router_publico = APIRouter(tags=["auth"])

router = APIRouter(tags=["auth"], dependencies=[Depends(get_current_user)])


@router_publico.post("/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    try:
        return LoginUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router_publico.post("/auth/esqueci-senha")
def esqueci_senha(request: SolicitarRecuperacaoRequest, db: Session = Depends(get_db)):
    """Dispara o e-mail com o link de redefinição.

    🔒 Responde SEMPRE a mesma coisa, exista o e-mail ou não. Devolver
    "e-mail não encontrado" transformaria esta rota pública num verificador de
    quem é membro do núcleo.
    """
    try:
        return SolicitarRecuperacaoUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        # Só chega aqui se o SMTP não estiver configurado — a regra de negócio
        # do fluxo em si nunca levanta erro, por decisão acima.
        raise HTTPException(status_code=422, detail=str(e))


@router_publico.post("/auth/redefinir-senha")
def redefinir_senha(request: RedefinirSenhaRequest, db: Session = Depends(get_db)):
    """Troca a senha usando o token de uso único que veio no e-mail."""
    try:
        return RedefinirSenhaUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/auth/registrar")
def registrar(request: RegistrarRequest, _=Depends(require_diretor), db: Session = Depends(get_db)):
    """§10: ninguém se auto-registra — os membros entram pré-cadastrados.

    🔒 Antes disto, qualquer pessoa logada criava uma conta e escolhia a
    `posicao` dela: um consultor podia se promover a diretor criando um
    usuário novo. Agora é ação de diretoria.
    """
    try:
        return RegistrarUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/auth/renovar")
def renovar(current_user=Depends(get_current_user)):
    """Devolve um token novo, com o prazo cheio, para quem já está logado.

    ⭐ É o que faz a sessão ser deslizante: o front chama isto toda vez que a
    plataforma abre, então quem usa o ATLAS regularmente nunca é deslogado no
    meio do trabalho. O prazo do `ACCESS_TOKEN_EXPIRE_MINUTES` passa a valer
    para sessão ABANDONADA — que é o caso em que ele deve mesmo expirar.

    Não é refresh token: não há um segundo segredo nem armazenamento de
    sessão. É o mesmo access token, reemitido enquanto o atual ainda vale —
    token expirado não chega aqui, o `get_current_user` recusa antes.
    """
    return {
        "access_token": criar_access_token(current_user.id),
        "token_type": "bearer",
    }


@router.get("/auth/me")
def get_me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "nome": current_user.nome,
        "email_insper": current_user.email_insper,
        "cargo_id": current_user.cargo_id,
        # `posicao` é o que o front usa para o recorte de visão e para a matriz
        # do §3; `cargo_id` continua valendo só para as ações de banca.
        "posicao": current_user.posicao,
        "status": current_user.status,
        "ativo": current_user.ativo,
    }
