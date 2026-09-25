from typing import List, Optional

from src.models.token_aprovacao_contratual_model import TokenAprovacaoContratualModel
from src.repositories.base_repository import BaseRepository


class TokenAprovacaoContratualRepository(BaseRepository[TokenAprovacaoContratualModel]):
    model = TokenAprovacaoContratualModel

    def get_by_token(self, token: str) -> Optional[TokenAprovacaoContratualModel]:
        return self.first_by(token=token)

    def list_by_documento(self, documento_id: int) -> List[TokenAprovacaoContratualModel]:
        """Todos os tokens de um documento, usados ou não — diferente de
        `get_ativo_por_documento`, que só acha o ativo. Quem precisa é o
        hard delete (`hard_deletar_documento.py`): tem que apagar o
        histórico inteiro, não só o link em aberto."""
        return self.filter_by(documento_id=documento_id)

    def get_ativo_por_documento(self, documento_id: int) -> Optional[TokenAprovacaoContratualModel]:
        """⭐ 2026-09-23 — a pedido: o link/card de "enviar ao cliente" tem que
        continuar na tela mesmo depois de sair e voltar (não é visualização
        única) — precisa achar o token de novo, não só devolver o que o
        `exportar-aprovacao` retornou na hora. `usado=False` já cobre "some
        quando o cliente responde": é o mesmo campo que marca o link como
        gasto (`aprovacao_publica.py`), então o próximo GET simplesmente não
        acha mais nenhum token ativo pra este documento."""
        return (
            self.db.query(self.model)
            .filter(self.model.documento_id == documento_id, self.model.usado.is_(False))
            .order_by(self.model.id.desc())
            .first()
        )

    def marcar_usado(self, registro: TokenAprovacaoContratualModel) -> TokenAprovacaoContratualModel:
        registro.usado = True
        self.db.commit()
        self.db.refresh(registro)
        return registro
