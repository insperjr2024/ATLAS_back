"""Tipos e status de um documento jurídico (§ Contratos).

Um "documento contratual" é o Contrato de Prestação de Serviços, o TEP, o
NDA, o Termo de Uso de Imagem ou um Termo Aditivo — sempre pendurado num
`ProjetoModel` do ATLAS, nunca numa pasta própria (ver o docstring de
`DocumentoContratualModel`).

⭐ 2026-09-16 — porta de `contratos-backend/src/entities/contrato.py`. Mesmo
papel de `status_projeto.py` pro pipeline de projeto: fonte única dos status
e dos conjuntos de permissão por status, pra não duplicar o mesmo set de
string solta em cada use case que precisa checar "pode gerar de novo?",
"pode editar?", "pode exportar?".

Os membros são `str, Enum`, então comparam e hasheiam como a string crua que
vai pro banco: `documento.status in STATUS_GERACAO_PERMITIDA` funciona sem
conversão.
"""

from enum import Enum


class TipoDocumentoContratual(str, Enum):
    CONTRATO = "contrato"
    TEP = "tep"
    NDA = "nda"
    USO_IMAGEM = "uso_imagem"
    ADITIVO = "aditivo"
    # Só existe via Importar Antigo (documento já assinado, sem fluxo de
    # geração) — projeto institucional (marketing, parceria) ou contrato
    # antigo de cliente que não se encaixa nos tipos fixos. Não tem redação
    # própria, por isso carrega uma descrição livre em `dados`.
    OUTRO = "outro"


class StatusDocumentoContratual(str, Enum):
    AGUARDANDO_PREENCHIMENTO = "aguardando_preenchimento"
    EM_REVISAO_INTERNA = "em_revisao_interna"
    AGUARDANDO_APROVACAO_CLIENTE = "aguardando_aprovacao_cliente"
    ALTERACAO_SOLICITADA = "alteracao_solicitada"
    #: Documento pronto, cliente já aprovou o texto — só falta ser assinado
    #: fora da plataforma e marcado como tal.
    APROVADO_PELO_CLIENTE = "aprovado_pelo_cliente"
    ASSINADO_E_ARQUIVADO = "assinado_e_arquivado"


#: O Contrato de Prestação é a raiz do projeto: os demais tipos herdam dele
#: os dados do CONTRATANTE, então nenhum pode existir antes dele.
TIPO_RAIZ = TipoDocumentoContratual.CONTRATO

#: Tipos que podem ser abertos dentro de um projeto já existente.
TIPOS_ADICIONAIS = frozenset({
    TipoDocumentoContratual.TEP,
    TipoDocumentoContratual.NDA,
    TipoDocumentoContratual.USO_IMAGEM,
    TipoDocumentoContratual.ADITIVO,
})

#: Ordem canônica de exibição (Repositório, aba Contratos do projeto).
ORDEM_TIPOS = (
    TipoDocumentoContratual.CONTRATO,
    TipoDocumentoContratual.ADITIVO,
    TipoDocumentoContratual.NDA,
    TipoDocumentoContratual.USO_IMAGEM,
    TipoDocumentoContratual.TEP,
    TipoDocumentoContratual.OUTRO,
)


# ---------- Conjuntos de status ----------

#: Gerar um novo rascunho: antes de o cliente ter aprovado.
STATUS_GERACAO_PERMITIDA = frozenset({
    StatusDocumentoContratual.AGUARDANDO_PREENCHIMENTO,
    StatusDocumentoContratual.EM_REVISAO_INTERNA,
    StatusDocumentoContratual.ALTERACAO_SOLICITADA,
})

#: Editar o texto do .docx à mão: só com um rascunho já gerado em revisão.
STATUS_EDICAO_TEXTO = frozenset({
    StatusDocumentoContratual.EM_REVISAO_INTERNA,
    StatusDocumentoContratual.ALTERACAO_SOLICITADA,
})

#: Mandar o link de aprovação pro cliente.
STATUS_EXPORTACAO_PERMITIDA = frozenset({StatusDocumentoContratual.EM_REVISAO_INTERNA})

#: A partir daqui o cliente já aprovou o documento gerado com estes dados —
#: editar invalidaria a aprovação dada. Regra de ciclo de vida, não de
#: permissão: vale pra todo mundo, inclusive diretoria.
STATUS_DADOS_TRAVADOS = frozenset({
    StatusDocumentoContratual.APROVADO_PELO_CLIENTE,
    StatusDocumentoContratual.ASSINADO_E_ARQUIVADO,
})

#: Cláusula de aceite tácito do TEP (Cláusula 4ª, Parágrafo Único): se o
#: cliente não assina em N dias corridos contados de quando o TEP fica
#: pronto para assinatura, o TEP se considera aceito. Nunca é automático —
#: só libera um botão pro time confirmar manualmente depois de vencido.
PRAZO_ACEITE_TACITO_TEP_DIAS = 20


def ordenar_por_tipo(tipos):
    """Ordena tipos pela ORDEM_TIPOS; desconhecidos vão pro fim."""
    indice = {t.value: i for i, t in enumerate(ORDEM_TIPOS)}
    return sorted(tipos, key=lambda t: indice.get(str(t), len(indice)))
