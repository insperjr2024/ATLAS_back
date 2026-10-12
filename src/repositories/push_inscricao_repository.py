from datetime import datetime
from typing import List, Optional

from src.models.push_inscricao_model import PushInscricaoModel
from src.repositories.base_repository import BaseRepository


class PushInscricaoRepository(BaseRepository[PushInscricaoModel]):
    model = PushInscricaoModel

    def get_by_usuario(self, usuario_id: int) -> List[PushInscricaoModel]:
        return self.filter_by(usuario_id=usuario_id)

    def get_by_endpoint(self, endpoint: str) -> Optional[PushInscricaoModel]:
        return self.first_by(endpoint=endpoint)

    def salvar(self, *, usuario_id: int, endpoint: str, p256dh: str, auth: str, user_agent: Optional[str]):
        """Cria ou atualiza pelo `endpoint`. Se o aparelho era de outra
        pessoa, passa a ser de quem acabou de ativar."""
        existente = self.get_by_endpoint(endpoint)
        if existente:
            existente.usuario_id = usuario_id
            existente.p256dh = p256dh
            existente.auth = auth
            existente.user_agent = user_agent
            self.db.commit()
            self.db.refresh(existente)
            return existente
        return self.create(
            usuario_id=usuario_id, endpoint=endpoint, p256dh=p256dh, auth=auth, user_agent=user_agent
        )

    def remover_por_endpoint(self, endpoint: str, usuario_id: Optional[int] = None) -> bool:
        query = self.db.query(PushInscricaoModel).filter(PushInscricaoModel.endpoint == endpoint)
        if usuario_id is not None:
            query = query.filter(PushInscricaoModel.usuario_id == usuario_id)
        apagadas = query.delete(synchronize_session=False)
        self.db.commit()
        return apagadas > 0

    def marcar_envio(self, ids: List[int], quando: datetime) -> None:
        if not ids:
            return
        self.db.query(PushInscricaoModel).filter(PushInscricaoModel.id.in_(ids)).update(
            {PushInscricaoModel.ultimo_envio_em: quando}, synchronize_session=False
        )
        self.db.commit()
