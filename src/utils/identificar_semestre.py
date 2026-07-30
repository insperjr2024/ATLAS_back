from datetime import datetime
from typing import List, Optional
from src.models.semestre_model import SemestreModel


def identificar_semestre(data_hora: datetime, semestres: List[SemestreModel]) -> Optional[SemestreModel]:
    data = data_hora.date()
    for semestre in semestres:
        if semestre.inicio <= data <= semestre.fim:
            return semestre
    return None