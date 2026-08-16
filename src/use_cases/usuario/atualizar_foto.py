"""Foto de perfil: sempre a PRÓPRIA, nunca a de outra pessoa.

Ao contrário de `UpdateUsuarioUseCase` (gerir membros, ação da diretoria),
trocar a foto é autoatendimento — não tem `usuario_id` no request, é sempre
`current_user.id`. Dar um `usuario_id` explícito deixaria qualquer pessoa
sobrescrever a foto de qualquer outra.
"""

import base64
import re

from sqlalchemy.orm import Session

from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.usuario.get_usuario import serializar_usuario
from src.utils.exceptions import RegraDeNegocioError

#: 2MB de base64 já é generoso para um avatar redimensionado no cliente
#: (~200x200, JPEG) — o limite existe para não deixar a coluna crescer sem
#: controle se algum dia o redimensionamento do front for pulado ou falhar.
TAMANHO_MAXIMO_BASE64 = 2 * 1024 * 1024

FORMATO_DATA_URI = re.compile(r"^data:image/(png|jpeg|jpg|webp);base64,")


class AtualizarFotoUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, current_user, foto: str):
        if len(foto) > TAMANHO_MAXIMO_BASE64:
            raise RegraDeNegocioError("Imagem grande demais. Escolha uma foto menor.")
        if not FORMATO_DATA_URI.match(foto):
            raise RegraDeNegocioError("Formato de imagem não reconhecido.")

        corpo = foto.split(",", 1)[1]
        try:
            base64.b64decode(corpo, validate=True)
        except Exception:
            raise RegraDeNegocioError("Imagem corrompida, tente enviar de novo.")

        usuario = self.repository.update(current_user.id, foto=foto)
        return serializar_usuario(usuario)


class RemoverFotoUsuarioUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self, current_user):
        usuario = self.repository.update(current_user.id, foto=None)
        return serializar_usuario(usuario)
