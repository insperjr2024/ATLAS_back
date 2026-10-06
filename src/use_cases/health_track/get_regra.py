from typing import Optional

from sqlalchemy.orm import Session

from src.models.usuario_model import UsuarioModel
from src.repositories.health_track_regra_repository import HealthTrackRegraRepository
from src.utils.health_track_status import faixa_amarela, para_regra


def serializar_regra(versao, usuarios: dict) -> dict:
    autor = usuarios.get(versao.criado_por)
    return {
        "id": versao.id,
        "verde": {
            "max_amarelos": versao.verde_max_amarelos,
            "max_vermelhos": versao.verde_max_vermelhos,
        },
        # Calculado, não editável: amarelo é o que não é verde nem vermelho.
        "amarelo": faixa_amarela(para_regra(versao)),
        "vermelho": {
            "min_amarelos": versao.vermelho_min_amarelos,
            "min_vermelhos": versao.vermelho_min_vermelhos,
        },
        "vigente_desde": versao.vigente_desde,
        "criado_por": versao.criado_por,
        "criado_por_nome": autor.nome if autor else None,
    }


def autores(db: Session, versoes) -> dict:
    ids = {v.criado_por for v in versoes if v.criado_por}
    return {u.id: u for u in db.query(UsuarioModel).filter(UsuarioModel.id.in_(ids or [-1]))}


class GetRegraUseCase:
    """A regra que vale agora — a última versão."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = HealthTrackRegraRepository(db)

    def execute(self) -> Optional[dict]:
        versoes = self.repository.get_versoes()
        if not versoes:
            return None
        atual = versoes[-1]
        return serializar_regra(atual, autores(self.db, [atual]))


class GetHistoricoRegraUseCase:
    """Todas as versões, da mais nova para a mais antiga — é o que permite à
    tela explicar por que um ciclo antigo tem status diferente "na época" e
    "pela regra atual"."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = HealthTrackRegraRepository(db)

    def execute(self) -> list[dict]:
        versoes = list(reversed(self.repository.get_versoes()))
        usuarios = autores(self.db, versoes)
        return [serializar_regra(v, usuarios) for v in versoes]
