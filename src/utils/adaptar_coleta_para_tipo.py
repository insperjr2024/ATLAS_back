"""Traduz o resultado da Coleta de Dados (sempre no formato do Contrato de
Prestação de Serviços) pro formato do tipo de documento pedido (§ Contratos).

⭐ 2026-09-18 — porta de `adaptar_coleta_para_tipo`/`CAMPOS_HERDADOS_POR_TIPO`
em `contratos-backend/src/use_cases/projeto/avancar_status.py`. É o mesmo
pré-preenchimento de `AbrirDocumentoContratualUseCase` — a diferença é a
fonte: lá, o Contrato de PS já salvo no projeto; aqui, o .docx que a pessoa
acabou de anexar. Com isso, qualquer documento pode nascer direto da Coleta,
sem precisar existir um Contrato de PS na plataforma pra herdar de.
"""

from typing import List, Tuple

from src.documentos_contratuais.extrair_coleta import PendenciaColeta
from src.utils.dados_documento_contratual import DADOS_INICIAIS_POR_TIPO

#: O que cada tipo ADICIONAL de fato aproveita da Coleta (espelha
#: `DADOS_INICIAIS_POR_TIPO`). Decide quais pendências da extração
#: interessam a cada documento: uma parcela que não deu pra ler não é
#: assunto do NDA, que não tem financeiro nenhum.
CAMPOS_HERDADOS_POR_TIPO = {
    "tep": ("contratante", "testemunhas", "projeto.escopos"),
    "nda": ("contratante", "testemunhas"),
    "uso_imagem": ("contratante", "testemunhas"),
    "aditivo": ("contratante", "testemunhas", "financeiro.valor_total"),
}


def adaptar_coleta_para_tipo(
    tipo: str, dados_contrato: dict, pendencias: List[PendenciaColeta], nome_projeto: str
) -> Tuple[dict, List[str]]:
    """`tipo == "contrato"` (ou desconhecido) devolve os dados como vieram —
    a Coleta já É o formato do Contrato de PS. Para os demais, usa o mesmo
    montador de `dados_iniciais_*` e filtra as pendências pelo que aquele
    tipo herda de fato."""
    montar = DADOS_INICIAIS_POR_TIPO.get(tipo)
    if montar is None:
        return dados_contrato, [p.mensagem for p in pendencias]

    prefixos = CAMPOS_HERDADOS_POR_TIPO.get(tipo, ())

    def interessa(campo: str) -> bool:
        return campo == "documento" or any(campo == p or campo.startswith(p + ".") for p in prefixos)

    return montar(dados_contrato, nome_projeto), [p.mensagem for p in pendencias if interessa(p.campo)]
