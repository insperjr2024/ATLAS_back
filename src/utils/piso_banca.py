from typing import List

from src.models.banca_model import BancaModel
from src.models.frente_model import FrenteModel


def calcular_piso_banca(banca: BancaModel, frentes_vinculadas: List[FrenteModel]) -> int:
    """O mínimo de pessoas exigido nesta banca (§8).

    `piso_minimo_override` (só a diretoria define) vale sobre o cálculo
    automático; sem override, é a soma do `piso_banca` de cada frente
    vinculada — uma banca sinérgica soma a exigência de cada frente.
    """
    if banca.piso_minimo_override is not None:
        return banca.piso_minimo_override
    return sum(f.piso_banca for f in frentes_vinculadas)
