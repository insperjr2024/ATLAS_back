from typing import List, Optional

import sqlalchemy as sa

from src.models.usuario_model import UsuarioModel
from src.repositories.base_repository import BaseRepository


class UsuarioRepository(BaseRepository[UsuarioModel]):
    model = UsuarioModel

    def get_by_email_insper(self, email_insper: str) -> Optional[UsuarioModel]:
        return self.first_by(email_insper=email_insper)

    def get_por_posicao(self, posicao: str) -> List[UsuarioModel]:
        return self.filter_by(posicao=posicao)

    def get_por_posicoes(self, *posicoes: str) -> List[UsuarioModel]:
        """Várias posições numa consulta só.

        Nasceu com a divisão da diretoria em três cargos: quase toda fila de
        aprovação notifica "a diretoria", que deixou de ser uma posição e virou
        um conjunto. O `filter_by` do `BaseRepository` só faz igualdade, e
        chamar `get_por_posicao` em laço daria uma query por cargo.
        """
        if not posicoes:
            return []
        return (
            self.db.query(self.model)
            .filter(self.model.posicao.in_(posicoes))
            .all()
        )

    def get_ativos(self) -> List[UsuarioModel]:
        return self.filter_by(status="ativo")

    def get_ativos_por_posicoes_ou_cargo_extra(self, posicoes) -> List[UsuarioModel]:
        """Quem TEM uma das posições, na base OU no `cargo_extra` — o mesmo
        OU de `usuario_tem_permissao` (`authorization.py`), só que pra achar
        as PESSOAS em vez de responder sim/não pra UMA pessoa. Usado por quem
        precisa notificar "todo mundo com a caixa X" (ex.: Jurídico em
        Contratos), não só checar quem está logado agora."""
        posicoes = set(posicoes)
        if not posicoes:
            return []
        return (
            self.db.query(self.model)
            .filter(
                self.model.status == "ativo",
                sa.or_(self.model.posicao.in_(posicoes), self.model.cargo_extra.in_(posicoes)),
            )
            .all()
        )