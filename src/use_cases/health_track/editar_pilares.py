"""Os pilares como configuração (Health Track §18): nome, descrição, ordem
de exibição e ativar/desativar. Só a diretoria de projetos mexe, como na
regra do status.

Pilar não se apaga: desativado some do preenchimento e do mapa, mas o
histórico dele continua existindo e precisando do nome.
"""

from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.repositories.health_track_pilar_repository import HealthTrackPilarRepository
from src.use_cases.health_track.serializar import serializar_pilar
from src.utils.exceptions import RegraDeNegocioError


class PilarRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    descricao: Optional[str] = None


class EditarPilarRequest(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=60)
    descricao: Optional[str] = None
    ordem: Optional[int] = Field(default=None, ge=0)
    ativo: Optional[bool] = None


class ListarTodosPilaresUseCase:
    """Inclusive os desativados, pra tela de configuração."""

    def __init__(self, db: Session):
        self.repository = HealthTrackPilarRepository(db)

    def execute(self) -> list[dict]:
        pilares = sorted(self.repository.get_all(), key=lambda p: (not p.ativo, p.ordem, p.id))
        return [serializar_pilar(p) for p in pilares]


class CriarPilarUseCase:
    def __init__(self, db: Session):
        self.repository = HealthTrackPilarRepository(db)

    def execute(self, request: PilarRequest) -> dict:
        nome = request.nome.strip()
        _nome_livre(self.repository, nome, None)
        ordem = max((p.ordem for p in self.repository.get_all()), default=-1) + 1
        pilar = self.repository.create(
            nome=nome, descricao=(request.descricao or "").strip() or None, ordem=ordem, ativo=True
        )
        return serializar_pilar(pilar)


class EditarPilarUseCase:
    def __init__(self, db: Session):
        self.repository = HealthTrackPilarRepository(db)

    def execute(self, pilar_id: int, request: EditarPilarRequest) -> dict:
        pilar = self.repository.get_by_id(pilar_id)
        if not pilar:
            raise RegraDeNegocioError("Pilar não encontrado")
        campos = {}
        if request.nome is not None:
            nome = request.nome.strip()
            _nome_livre(self.repository, nome, pilar_id)
            campos["nome"] = nome
        if request.descricao is not None:
            campos["descricao"] = request.descricao.strip() or None
        if request.ordem is not None:
            campos["ordem"] = request.ordem
        if request.ativo is not None:
            if not request.ativo and pilar.ativo:
                ativos = [p for p in self.repository.get_ativos() if p.id != pilar_id]
                if not ativos:
                    raise RegraDeNegocioError("O Health Track precisa de pelo menos um pilar ativo.")
            campos["ativo"] = request.ativo
        if campos:
            pilar = self.repository.update(pilar_id, **campos)
        return serializar_pilar(pilar)


def _nome_livre(repository: HealthTrackPilarRepository, nome: str, pilar_id: Optional[int]) -> None:
    for p in repository.get_all():
        if p.id != pilar_id and p.nome.strip().casefold() == nome.casefold():
            raise RegraDeNegocioError(f'Já existe um pilar chamado "{p.nome}".')
