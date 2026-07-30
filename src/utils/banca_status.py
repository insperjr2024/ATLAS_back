from datetime import datetime
from typing import Optional


def calcular_status_banca(data_hora: Optional[datetime]) -> str:
    if data_hora is None:
        return "aberta para inscrições"
    if datetime.now() >= data_hora:
        return "realizada"
    return "aberta para inscrições"