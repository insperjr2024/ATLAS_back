"""A ponte entre uma regra de negócio violada e a resposta HTTP."""

from fastapi import HTTPException

from src.utils.exceptions import RegraDeNegocioError


def erro_de_regra(erro: RegraDeNegocioError) -> HTTPException:
    """Transforma a recusa em 422, levando o `codigo` junto quando existe.

    ⭐ **O formato muda conforme a recusa tenha código ou não**, e isso é de
    propósito:

    - sem código → `{"detail": "texto"}`, exatamente como os 70 outros pontos
      da API que fazem `detail=str(e)`. Nada muda para quem já consome;
    - com código → `{"detail": {"msg": "texto", "codigo": "..."}}`.

    O segundo formato não quebra ninguém porque o `formatApiDetail` do front
    já sabe extrair `msg` de um objeto — quem só mostra a mensagem continua
    mostrando a mensagem, sem saber que existe um código.

    📐 Por que não trocar os 70 pontos de uma vez: código só serve onde a
    interface REAGE à recusa, e hoje isso é um lugar só. Converter tudo criaria
    setenta chamadas idênticas para carregar um campo que ninguém lê.
    """
    if getattr(erro, "codigo", None):
        return HTTPException(
            status_code=422, detail={"msg": str(erro), "codigo": erro.codigo}
        )
    return HTTPException(status_code=422, detail=str(erro))
