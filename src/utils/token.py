from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from src.config.config import get_settings


def criar_access_token(usuario_id: int, celular: bool = False) -> str:
    """`celular=True`: sessão longa (`ACCESS_TOKEN_CELULAR_DIAS`). Quem diz
    que é celular é o próprio front; não é trava de segurança, é conforto de
    quem já desbloqueou o aparelho."""
    settings = get_settings()
    prazo = (
        timedelta(days=settings.ACCESS_TOKEN_CELULAR_DIAS)
        if celular
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(usuario_id), "exp": datetime.now(timezone.utc) + prazo}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decodificar_access_token(token: str) -> Optional[int]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        usuario_id = payload.get("sub")
        return int(usuario_id) if usuario_id is not None else None
    except JWTError:
        return None