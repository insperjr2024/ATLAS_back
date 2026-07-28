from sqlalchemy.orm import Session
from src.repositories.formulario_repository import FormularioRepository


class GetFormularioUseCase:
    def __init__(self, db: Session):
        self.repository = FormularioRepository(db)

    def execute(self, formulario_id: int):
        formulario = self.repository.get_by_id(formulario_id)
        if not formulario:
            return None
        return {"id": formulario.id, "semestre_id": formulario.semestre_id, "ativo": formulario.ativo}


class ListFormulariosUseCase:
    def __init__(self, db: Session):
        self.repository = FormularioRepository(db)

    def execute(self):
        formularios = self.repository.get_all()
        return [
            {"id": f.id, "semestre_id": f.semestre_id, "ativo": f.ativo}
            for f in formularios
        ]