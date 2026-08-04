from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from src.database.database import get_db
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.token import decodificar_access_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    usuario_id = decodificar_access_token(credentials.credentials)
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    usuario = UsuarioRepository(db).get_by_id(usuario_id)
    if not usuario or not usuario.ativo:
        raise HTTPException(status_code=401, detail="Usuário não encontrado ou inativo")

    return usuario