from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.formulario_repository import FormularioRepository


class UpdateFormularioRequest(BaseModel):
    semestre_id: Optional[int] = None
    ativo: Optional[bool] = None


class UpdateFormularioUseCase:
    def __init__(self, db: Session):
        self.repository = FormularioRepository(db)

    def execute(self, formulario_id: int, request: UpdateFormularioRequest):
        data = request.dict(exclude_unset=True)
        formulario = self.repository.update(formulario_id, **data)
        if not formulario:
            return None
        return {"id": formulario.id, "semestre_id": formulario.semestre_id, "ativo": formulario.ativo}


class DeleteFormularioUseCase:
    def __init__(self, db: Session):
        self.repository = FormularioRepository(db)

    def execute(self, formulario_id: int) -> bool:
        return self.repository.delete(formulario_id)