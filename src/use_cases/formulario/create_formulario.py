from sqlalchemy.orm import Session
from src.repositories.formulario_repository import FormularioRepository
from pydantic import BaseModel


class CreateFormularioRequest(BaseModel):
    semestre_id: int
    ativo: bool = True


class CreateFormularioUseCase:
    def __init__(self, db: Session):
        self.repository = FormularioRepository(db)

    def execute(self, request: CreateFormularioRequest):
        formulario = self.repository.create(
            semestre_id=request.semestre_id,
            ativo=request.ativo
        )
        return {
            "id": formulario.id,
            "semestre_id": formulario.semestre_id,
            "ativo": formulario.ativo
        }