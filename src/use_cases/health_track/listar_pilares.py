from sqlalchemy.orm import Session

from src.repositories.health_track_pilar_repository import HealthTrackPilarRepository
from src.use_cases.health_track.serializar import serializar_pilar


class ListarPilaresUseCase:
    def __init__(self, db: Session):
        self.repository = HealthTrackPilarRepository(db)

    def execute(self) -> list[dict]:
        return [serializar_pilar(p) for p in self.repository.get_ativos()]
