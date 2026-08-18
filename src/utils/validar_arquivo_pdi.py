from src.utils.exceptions import RegraDeNegocioError

TAMANHO_MAXIMO_BYTES = 15 * 1024 * 1024  # 15MB

# Assinatura real do arquivo, não só a extensão — mesmo cuidado do anexo de
# proposta (evita gravar um arquivo renomeado que na verdade não é do tipo
# que diz ser). .docx é um zip (mesma assinatura de .xlsx/.pptx, mas não
# valida além disso — não é o objetivo aqui checar o conteúdo interno).
ASSINATURAS = {
    ".pdf": b"%PDF-",
    ".docx": b"PK\x03\x04",
    ".doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89PNG\r\n\x1a\n",
    # Mesma assinatura de .docx/.pptx (zip) e .doc (OLE) respectivamente —
    # quem discrimina é o nome do arquivo, não a assinatura (ver o comentário
    # acima sobre .docx).
    ".xlsx": b"PK\x03\x04",
    ".xls": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
}

# Quais extensões cada `tipo_arquivo` de item aceita (ver
# `DesempenhoPdiItemModel.tipo_arquivo`). "qualquer" existe pra itens que não
# precisam de restrição (o padrão criado pelas pastas antigas).
EXTENSOES_POR_TIPO = {
    "documento": {".pdf", ".docx", ".doc"},
    "foto": {".jpg", ".jpeg", ".png"},
    "planilha": {".xlsx", ".xls"},
    "qualquer": set(ASSINATURAS),
}

MENSAGEM_POR_TIPO = {
    "documento": "Este item precisa de um PDF ou Word (.doc/.docx)",
    "foto": "Este item precisa de uma foto (.jpg/.jpeg/.png)",
    "planilha": "Este item precisa de uma planilha Excel (.xlsx/.xls)",
    "qualquer": "O arquivo precisa ser um PDF, Word (.doc/.docx), Excel (.xlsx/.xls) ou uma foto (.jpg/.jpeg/.png)",
}


def validar_arquivo_pdi(nome_original: str, conteudo: bytes, tipo_arquivo: str = "qualquer") -> str:
    """Confere extensão + assinatura + tamanho de um envio de PDI, restrito
    ao `tipo_arquivo` do item (documento/foto/qualquer). Devolve a extensão
    validada (com ponto), pra quem chama montar o nome no disco."""
    permitidas = EXTENSOES_POR_TIPO.get(tipo_arquivo, EXTENSOES_POR_TIPO["qualquer"])
    nome = (nome_original or "").strip().lower()
    extensao = next((ext for ext in permitidas if nome.endswith(ext)), None)
    if not extensao:
        raise RegraDeNegocioError(MENSAGEM_POR_TIPO.get(tipo_arquivo, MENSAGEM_POR_TIPO["qualquer"]))

    if not conteudo:
        raise RegraDeNegocioError("O arquivo enviado está vazio")
    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        raise RegraDeNegocioError("O arquivo precisa ter até 15MB")

    assinatura = ASSINATURAS[extensao]
    if not conteudo.startswith(assinatura):
        raise RegraDeNegocioError("O arquivo enviado não corresponde ao tipo esperado")

    return extensao
