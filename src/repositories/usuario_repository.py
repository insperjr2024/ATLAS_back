from typing import List, Optional

from src.models.usuario_model import UsuarioModel
from src.repositories.base_repository import BaseRepository


class UsuarioRepository(BaseRepository[UsuarioModel]):
    model = UsuarioModel

    def get_by_email_insper(self, email_insper: str) -> Optional[UsuarioModel]:
        return self.first_by(email_insper=email_insper)

    def get_por_posicao(self, posicao: str) -> List[UsuarioModel]:
        return self.filter_by(posicao=posicao)

    def get_ativos(self) -> List[UsuarioModel]:
        return self.filter_by(status="ativo")