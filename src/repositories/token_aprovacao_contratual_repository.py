from typing import Optional

from src.models.token_aprovacao_contratual_model import TokenAprovacaoContratualModel
from src.repositories.base_repository import BaseRepository


class TokenAprovacaoContratualRepository(BaseRepository[TokenAprovacaoContratualModel]):
    model = TokenAprovacaoContratualModel

    def get_by_token(self, token: str) -> Optional[TokenAprovacaoContratualModel]:
        return self.first_by(token=token)

    def marcar_usado(self, registro: TokenAprovacaoContratualModel) -> TokenAprovacaoContratualModel:
        registro.usado = True
        self.db.commit()
        self.db.refresh(registro)
        return registro
