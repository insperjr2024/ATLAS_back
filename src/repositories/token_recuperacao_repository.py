from datetime import datetime
from typing import Optional

from src.models.token_recuperacao_model import TokenRecuperacaoModel
from src.repositories.base_repository import BaseRepository


class TokenRecuperacaoRepository(BaseRepository[TokenRecuperacaoModel]):
    model = TokenRecuperacaoModel

    def get_por_hash(self, token_hash: str) -> Optional[TokenRecuperacaoModel]:
        """Busca pelo sha256, que é indexado e único.

        É por isso que o hash é determinístico e não bcrypt: com salt seria
        preciso carregar todos os tokens e testar um a um.
        """
        return self.first_by(token_hash=token_hash)

    def get_ultimo_do_usuario(self, usuario_id: int) -> Optional[TokenRecuperacaoModel]:
        """O pedido mais recente, usado ou não — insumo do controle de spam."""
        return (
            self.db.query(self.model)
            .filter(self.model.usuario_id == usuario_id)
            .order_by(self.model.criado_em.desc())
            .first()
        )

    def invalidar_pendentes(self, usuario_id: int, quando: datetime) -> int:
        """Queima os tokens não usados do usuário e devolve quantos foram.

        Pedir um link novo tem que derrubar o anterior: senão dois e-mails
        ficam válidos ao mesmo tempo e o mais antigo — provavelmente o que
        vazou, já que é o que está há mais tempo na caixa — continua servindo.
        """
        pendentes = (
            self.db.query(self.model)
            .filter(
                self.model.usuario_id == usuario_id,
                self.model.usado_em.is_(None),
            )
            .all()
        )
        for token in pendentes:
            token.usado_em = quando
        self.db.commit()
        return len(pendentes)

    def marcar_usado(self, token: TokenRecuperacaoModel, quando: datetime) -> None:
        """Fecha o token. É o que o torna de uso único."""
        token.usado_em = quando
        self.db.commit()
