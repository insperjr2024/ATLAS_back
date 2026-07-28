from sqlalchemy.orm import Session
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository


class GetUsuarioFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioFrenteRepository(db)

    def execute(self, usuario_frente_id: int):
        uf = self.repository.get_by_id(usuario_frente_id)
        if not uf:
            return None
        return {"id": uf.id, "usuario_id": uf.usuario_id, "frente_id": uf.frente_id}


class ListUsuariosFrentesUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioFrenteRepository(db)

    def execute(self):
        registros = self.repository.get_all()
        return [{"id": r.id, "usuario_id": r.usuario_id, "frente_id": r.frente_id} for r in registros]