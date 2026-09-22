"""A ponte entre uma regra de negócio violada e a resposta HTTP."""

from fastapi import HTTPException

from src.utils.exceptions import RegraDeNegocioError


def erro_de_regra(erro: RegraDeNegocioError) -> HTTPException:
    """Transforma a recusa em 422, levando `codigo`/`campos` junto quando existem.

    ⭐ **O formato muda conforme a recusa carregue algo além do texto**, e isso
    é de propósito:

    - sem nada extra → `{"detail": "texto"}`, exatamente como os outros
      pontos da API que fazem `detail=str(e)`. Nada muda para quem já consome;
    - com `codigo` e/ou `campos` → `{"detail": {"msg": "texto", ...}}`.

    O segundo formato não quebra ninguém porque o `formatApiDetail` do front
    já sabe extrair `msg` de um objeto — quem só mostra a mensagem continua
    mostrando a mensagem, sem saber que existe algo mais.

    📐 Por que não trocar todos os pontos de uma vez: isso só serve onde a
    interface REAGE à recusa (troca de tela, destaque de campo), e hoje são
    poucos lugares. Converter tudo criaria dezenas de chamadas idênticas para
    carregar um campo que ninguém lê.
    """
    codigo = getattr(erro, "codigo", None)
    campos = getattr(erro, "campos", None)
    if codigo or campos:
        detail: dict = {"msg": str(erro)}
        if codigo:
            detail["codigo"] = codigo
        if campos:
            detail["campos"] = campos
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=422, detail=str(erro))
