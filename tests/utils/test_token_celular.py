"""Sessão longa no celular (2026-10-12): o token do celular vale dias, o do
computador segue os minutos de sempre."""

from datetime import datetime, timezone

from jose import jwt

from src.config.config import get_settings
from src.utils.token import criar_access_token, decodificar_access_token


def _horas_ate_expirar(token: str) -> float:
    s = get_settings()
    exp = jwt.decode(token, s.SECRET_KEY, algorithms=[s.ALGORITHM])["exp"]
    return (exp - datetime.now(timezone.utc).timestamp()) / 3600


def test_computador_expira_em_minutos():
    horas = _horas_ate_expirar(criar_access_token(7))

    assert horas <= get_settings().ACCESS_TOKEN_EXPIRE_MINUTES / 60 + 0.01


def test_celular_dura_dias():
    horas = _horas_ate_expirar(criar_access_token(7, celular=True))

    assert horas >= (get_settings().ACCESS_TOKEN_CELULAR_DIAS - 1) * 24


def test_os_dois_identificam_a_mesma_pessoa():
    assert decodificar_access_token(criar_access_token(7, celular=True)) == 7
    assert decodificar_access_token(criar_access_token(7)) == 7
