from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import require_diretor
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.auth.login import LoginUseCase, LoginRequest
from src.use_cases.auth.registrar import RegistrarUseCase, RegistrarRequest
from src.utils.exceptions import RegraDeNegocioError

# Rotas sem token: só o login. O registro fica no router protegido abaixo —
# o §10 do briefing é explícito em que ninguém se auto-registra.
router_publico = APIRouter(tags=["auth"])

router = APIRouter(tags=["auth"], dependencies=[Depends(get_current_user)])


@router_publico.post("/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    try:
        return LoginUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=401, detail=str(e))


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
