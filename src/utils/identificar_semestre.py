from datetime import datetime
from typing import List, Optional
from src.models.semestre_model import SemestreModel


def identificar_semestre(data_hora: Optional[datetime], semestres: List[SemestreModel]) -> Optional[SemestreModel]:
    # Banca ainda `nao_marcada` tem `data_hora` nula de propósito (ver
    # `banca_model`), e sem data não há semestre a identificar. Antes disto,
    # uma única banca não marcada derrubava a lista inteira com 500.
    if data_hora is None:
        return None
    data = data_hora.date()
    for semestre in semestres:
        if semestre.inicio <= data <= semestre.fim:
            return semestre
    return None