from typing import Optional

from src.models.desempenho_criterio_model import DesempenhoCriterioModel
from src.utils.exceptions import RegraDeNegocioError


def validar_desempenho_nota(
    criterio: DesempenhoCriterioModel, nota: Optional[int], resposta_texto: Optional[str]
) -> None:
    if criterio.tipo_resposta == "nota":
        if nota is None:
            raise RegraDeNegocioError(f"O critério '{criterio.label}' exige uma nota de 1 a 5")
        if resposta_texto is not None:
            raise RegraDeNegocioError(f"O critério '{criterio.label}' não aceita resposta em texto")
        if nota < 1 or nota > 5:
            raise RegraDeNegocioError(f"A nota do critério '{criterio.label}' deve estar entre 1 e 5")

    elif criterio.tipo_resposta == "texto":
        if not resposta_texto:
            raise RegraDeNegocioError(f"O critério '{criterio.label}' exige uma resposta em texto")
        if nota is not None:
            raise RegraDeNegocioError(f"O critério '{criterio.label}' não aceita nota")
        if criterio.limite_caracteres and len(resposta_texto) > criterio.limite_caracteres:
            raise RegraDeNegocioError(
                f"A resposta do critério '{criterio.label}' excede {criterio.limite_caracteres} caracteres"
            )
