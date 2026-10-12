"""Gera o par de chaves VAPID da notificação push.

    uv run python -m scripts.gerar_chaves_vapid

Imprime as duas linhas pra colar no `.env` (local) e nas variáveis do
Railway (produção). Gere UMA vez por ambiente e não troque depois: trocar a
chave invalida todos os aparelhos já ativados, e cada pessoa teria de ativar
de novo.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def main() -> None:
    privada = ec.generate_private_key(ec.SECP256R1())
    bruta = privada.private_numbers().private_value.to_bytes(32, "big")
    publica = privada.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    print(f"VAPID_PUBLIC_KEY={_b64url(publica)}")
    print(f"VAPID_PRIVATE_KEY={_b64url(bruta)}")


if __name__ == "__main__":
    main()
