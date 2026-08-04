"""A trava do cronograma oficializado (§5.6).

"Alterar um cronograma já oficializado exige solicitação do coordenador,
aprovada pela diretoria. Deve ser exceção, não rotina."

A checagem mora **aqui**, num lugar só, e é chamada por todo use case de
escrita de etapa e marco — não repetida em cinco rotas.

Devolve **409**, não 422: é conflito de estado (o recurso está travado), não
erro de validação do que foi enviado. O front usa essa diferença para
oferecer "solicitar reajuste" em vez de um toast vermelho genérico.
"""

from fastapi import HTTPException


class CronogramaOficializadoError(Exception):
    """O escopo já teve o cronograma cravado — mudança vira reajuste (F11)."""


def exigir_cronograma_editavel(projeto_escopo) -> None:
    if projeto_escopo.cronograma_oficializado_em is not None:
        raise CronogramaOficializadoError()


def http_conflito_cronograma() -> HTTPException:
    """O 409 padronizado, com `codigo` para o front reagir sem parsear texto."""
    return HTTPException(
        status_code=409,
        detail={
            "codigo": "cronograma_oficializado",
            "mensagem": (
                "Este cronograma já foi oficializado. Alterá-lo exige uma "
                "solicitação de reajuste aprovada pela diretoria (§5.6)."
            ),
        },
    )
