from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from src.config.config import get_settings


def criar_access_token(usuario_id: int) -> str:
    settings = get_settings()
    expira_em = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(usuario_id), "exp": expira_em}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decodificar_access_token(token: str) -> Optional[int]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        usuario_id = payload.get("sub")
        return int(usuario_id) if usuario_id is not None else None
    except JWTError:
        return None