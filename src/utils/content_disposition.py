"""O cabeçalho Content-Disposition de um download, seguro pra qualquer nome.

Cabeçalho HTTP só aceita latin-1, e o Starlette estoura ao codificar o que
não cabe nele (2026-10-13, corrigido): "Captura de Tela ... às ...png", o
nome que o Mac dá à captura, vem com o acento como caractere separado da
letra (forma NFD), que não existe em latin-1. O download respondia 500 e a
tela dizia só "Erro ao baixar o arquivo".

Resposta no formato da RFC 6266: `filename` com uma versão só ASCII, pra
cliente antigo, e `filename*` em UTF-8 percent-encoded, que é o que o
navegador usa pra dar ao arquivo o nome de verdade.
"""

import unicodedata
from urllib.parse import quote


def content_disposition(nome: str, inline: bool = False) -> str:
    nome = (nome or "").strip() or "arquivo"
    # NFC junta acento e letra; o fallback ASCII tira o que sobrar de fora.
    nfc = unicodedata.normalize("NFC", nome)
    ascii_ = (
        unicodedata.normalize("NFKD", nfc)
        .encode("ascii", "ignore")
        .decode()
        .replace('"', "")
        .replace("\\", "")
        .replace("\r", "")
        .replace("\n", "")
        .strip()
    ) or "arquivo"
    tipo = "inline" if inline else "attachment"
    return f"{tipo}; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nfc, safe='')}"
