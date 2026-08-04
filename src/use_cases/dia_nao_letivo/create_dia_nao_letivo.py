from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.semestre_repository import SemestreRepository
from src.utils.exceptions import RegraDeNegocioError

TipoDiaNaoLetivo = Literal["feriado", "prova", "recesso"]


class DiaNaoLetivoItem(BaseModel):
    data: date
    tipo: TipoDiaNaoLetivo = "feriado"
    descricao: Optional[str] = None


class CreateDiasNaoLetivosRequest(BaseModel):
    """Carga em lote: a diretoria sobe o calendário do semestre de uma vez."""

    dias: List[DiaNaoLetivoItem]
    substituir: bool = False


class CreateDiasNaoLetivosUseCase:
    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, semestre_id: int, request: CreateDiasNaoLetivosRequest):
        semestre = self.semestre_repository.get_by_id(semestre_id)
        if not semestre:
            raise RegraDeNegocioError("Semestre não encontrado")

        if request.substituir:
            self.repository.delete_por_semestre(semestre_id)

        existentes = {d.data for d in self.repository.get_by_semestre(semestre_id)}

        criados, ignorados = [], []
        for item in request.dias:
            if not (semestre.inicio <= item.data <= semestre.fim):
                raise RegraDeNegocioError(
                    f"{item.data:%d/%m/%Y} está fora do semestre "
                    f"{semestre.nome} ({semestre.inicio:%d/%m/%Y} a {semestre.fim:%d/%m/%Y})"
                )
            # Recarregar o calendário não pode explodir no unique: o dia que já
            # está lá é só ignorado.
            if item.data in existentes:
                ignorados.append(item.data)
                continue
            registro = self.repository.create(
                semestre_id=semestre_id,
                data=item.data,
                tipo=item.tipo,
                descricao=item.descricao,
            )
            existentes.add(item.data)
            criados.append(registro)

        return {
            "semestre_id": semestre_id,
            "criados": len(criados),
            "ignorados": len(ignorados),
            "dias": [
                {
                    "id": d.id,
                    "data": d.data,
                    "tipo": d.tipo,
                    "descricao": d.descricao,
                }
                for d in criados
            ],
        }
