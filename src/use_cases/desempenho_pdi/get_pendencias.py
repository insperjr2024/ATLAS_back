from sqlalchemy.orm import Session

from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository
from src.repositories.desempenho_pdi_envio_repository import DesempenhoPdiEnvioRepository
from src.repositories.usuario_repository import UsuarioRepository


class ListPendenciasPdiUseCase:
    """Quem ainda não enviou o arquivo deste ITEM (não mais a pasta inteira
    — cada item da checklist tem sua própria pendência). O universo é todo
    mundo com mentoria vinculada."""

    def __init__(self, db: Session):
        self.mentoria_repository = DesempenhoMentoriaRepository(db)
        self.envio_repository = DesempenhoPdiEnvioRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self, item_id: int) -> list[dict]:
        enviados = {e.mentorado_id for e in self.envio_repository.get_por_item(item_id)}
        nomes = {u.id: u.nome for u in self.usuario_repo.get_all()}
        return [
            {
                "mentorado_id": m.mentorado_id,
                "mentorado_nome": nomes.get(m.mentorado_id),
                "mentor_id": m.mentor_id,
                "mentor_nome": nomes.get(m.mentor_id),
            }
            for m in self.mentoria_repository.get_all()
            if m.mentorado_id not in enviados
        ]
