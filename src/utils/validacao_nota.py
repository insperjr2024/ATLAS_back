from decimal import Decimal
from typing import Optional
from src.models.pergunta_model import PerguntaModel
from src.utils.exceptions import RegraDeNegocioError


def validar_avaliacao_nota(pergunta: PerguntaModel, nota: Optional[Decimal], resposta_texto: Optional[str]):
    if pergunta.tipo_resposta == "nota":
        if nota is None:
            raise RegraDeNegocioError("Esta pergunta exige uma nota (0 a 5, variando de 0.5)")
        if resposta_texto is not None:
            raise RegraDeNegocioError("Esta pergunta não aceita resposta discursiva")
        if nota < 0 or nota > 5:
            raise RegraDeNegocioError("A nota deve estar entre 0 e 5")
        if (nota * 2) % 1 != 0:
            raise RegraDeNegocioError("A nota deve variar de 0.5 em 0.5 (ex: 0, 0.5, 1, 1.5...)")

    elif pergunta.tipo_resposta == "dissertativa":
        if not resposta_texto:
            raise RegraDeNegocioError("Esta pergunta exige uma resposta discursiva")
        if nota is not None:
            raise RegraDeNegocioError("Esta pergunta não aceita nota")