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
    #: ⭐ 2026-09-21 — a pedido: separa "o Jurídico aprovou por dentro" de
    #: "gerou o rascunho". Antes das duas coisas eram a mesma permissão —
    #: agora só depois desta aprovação é que dá para exportar/mandar pro
    #: cliente (`STATUS_EXPORTACAO_PERMITIDA`), e quem manda pode ser gente
    #: de fora do Jurídico (vendedor do projeto no Contrato de Prestação,
    #: diretor de projetos/coordenador no TEP — ver `_pode_enviar_ao_cliente`
    #: em `routers/documentos_contratuais.py`).
    APROVADO_INTERNAMENTE = "aprovado_internamente"
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

#: Rótulo amigável do tipo — usado nas notificações e em qualquer tela que
#: precise nomear o documento pra gente, não pro sistema.
ROTULO_TIPO = {
    TipoDocumentoContratual.CONTRATO.value: "Contrato de Prestação de Serviços",
    TipoDocumentoContratual.TEP.value: "Termo de Encerramento de Projeto",
    TipoDocumentoContratual.NDA.value: "Acordo de Confidencialidade",
    TipoDocumentoContratual.USO_IMAGEM.value: "Termo de Uso de Imagem",
    TipoDocumentoContratual.ADITIVO.value: "Termo Aditivo",
    TipoDocumentoContratual.OUTRO.value: "Documento",
}


# ---------- Conjuntos de status ----------

#: Gerar um novo rascunho: antes de o cliente ter aprovado. Regerar depois
#: de já aprovado internamente é permitido (o Jurídico pode ter pedido um
#: ajuste antes de mandar) — mas invalida a aprovação anterior, ver
#: `gerar_documento.py`.
STATUS_GERACAO_PERMITIDA = frozenset({
    StatusDocumentoContratual.AGUARDANDO_PREENCHIMENTO,
    StatusDocumentoContratual.EM_REVISAO_INTERNA,
    StatusDocumentoContratual.APROVADO_INTERNAMENTE,
    StatusDocumentoContratual.ALTERACAO_SOLICITADA,
})

#: Editar o texto do .docx à mão: um rascunho já gerado, em revisão ou já
#: aprovado internamente (idem acima, invalida a aprovação — ver
#: `editar_texto.py`/`reanexar_documento.py`).
STATUS_EDICAO_TEXTO = frozenset({
    StatusDocumentoContratual.EM_REVISAO_INTERNA,
    StatusDocumentoContratual.APROVADO_INTERNAMENTE,
    StatusDocumentoContratual.ALTERACAO_SOLICITADA,
})

#: Aprovar o rascunho por dentro (Jurídico) — só de quem ainda não passou
#: por isso.
STATUS_APROVACAO_INTERNA_PERMITIDA = frozenset({StatusDocumentoContratual.EM_REVISAO_INTERNA})

#: Mandar o link de aprovação pro cliente — só depois do Jurídico aprovar
#: por dentro (era só "em_revisao_interna", a mesma pessoa gerava e mandava).
STATUS_EXPORTACAO_PERMITIDA = frozenset({StatusDocumentoContratual.APROVADO_INTERNAMENTE})

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
#:
#: ⚠ 2026-09-18, corrigido: o texto real da cláusula (ver o .docx do
#: template) diz 5 dias corridos. O valor 20 veio de uma confusão com o
#: prazo de SUPORTE pós-aceite (20 dias ÚTEIS, Cláusula 18ª do Contrato de
#: PS) — outro prazo, contado a partir de outro marco — e foi portado por
#: engano junto com o resto na Fase 1. A fonte de verdade é o documento que
#: o cliente assina, não o valor que o sistema antigo usava.
PRAZO_ACEITE_TACITO_TEP_DIAS = 5


def ordenar_por_tipo(tipos):
    """Ordena tipos pela ORDEM_TIPOS; desconhecidos vão pro fim."""
    indice = {t.value: i for i, t in enumerate(ORDEM_TIPOS)}
    return sorted(tipos, key=lambda t: indice.get(str(t), len(indice)))
