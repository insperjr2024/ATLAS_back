"""Texto pronto pra mandar o documento jurídico ao cliente pelo WhatsApp.

⭐ 2026-09-18 — porta de `contratos-backend/src/utils/wa_link.py`. Não há
integração de envio nenhuma: a plataforma só monta o texto; quem manda baixa
o PDF e anexa por conta própria (ver `exportar_aprovacao.py`).

⭐ 2026-09-20 — o link `wa.me` (que precisa do telefone) saiu daqui: o número
cadastrado no formulário pode estar errado ou ser de outra pessoa, então quem
manda digita o número na hora, no front (`montarLinkWhatsapp` em
`lib/contratos.ts`) — o back só entrega este texto.
"""


def mensagem_aprovacao(nome_projeto: str, link_aprovacao: str) -> str:
    return (
        f'Olá! Segue em anexo (PDF) o documento referente ao projeto "{nome_projeto}" para sua revisão.\n\n'
        f"Você pode ver o documento e registrar a aprovação (ou solicitar algum ajuste, selecionando o "
        f"trecho direto no texto) por aqui:\n{link_aprovacao}\n\n"
        "Qualquer dúvida, fico à disposição."
    )
