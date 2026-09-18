"""Link de WhatsApp pronto pra mandar o documento jurídico ao cliente.

⭐ 2026-09-18 — porta de `contratos-backend/src/utils/wa_link.py`. Não há
integração de envio nenhuma: a plataforma só monta o link e o texto: quem
manda baixa o PDF e anexa por conta própria (ver `exportar_aprovacao.py`).
"""

import re
from urllib.parse import quote


def montar_link_whatsapp(telefone: str, mensagem: str) -> str:
    digitos = re.sub(r"\D", "", telefone)
    numero_completo = digitos if digitos.startswith("55") else f"55{digitos}"
    return f"https://wa.me/{numero_completo}?text={quote(mensagem)}"


def mensagem_aprovacao(nome_projeto: str, link_aprovacao: str) -> str:
    return (
        f'Olá! Segue em anexo (PDF) o documento referente ao projeto "{nome_projeto}" para sua revisão.\n\n'
        f"Você pode ver o documento e registrar a aprovação (ou solicitar algum ajuste, selecionando o "
        f"trecho direto no texto) por aqui:\n{link_aprovacao}\n\n"
        "Qualquer dúvida, fico à disposição."
    )
