"""Formata a linha de `IdentidadeInstitucionalModel` no shape que
`render_template.py` espera (§ Contratos).

⭐ 2026-09-16 — porta de `contratos-backend/src/utils/identidade_institucional.py`,
trocando `ConfiguracaoModel` (Contratos) por `IdentidadeInstitucionalModel`
(ATLAS) — mesmos campos, só o model de origem muda.
"""

from src.models.identidade_institucional_model import IdentidadeInstitucionalModel


def endereco_presidente_completo(identidade: IdentidadeInstitucionalModel) -> str:
    """Rua/número/complemento/bairro/cidade/estado/CEP cadastrados
    separados, juntados numa frase só — é o que o documento gerado espera
    (`{{ presidente.endereco }}` nos templates, uma string única)."""
    numero_complemento = identidade.presidente_endereco_numero
    if identidade.presidente_endereco_complemento:
        numero_complemento += f", {identidade.presidente_endereco_complemento}"
    return (
        f"{identidade.presidente_endereco_rua}, nº {numero_complemento}, "
        f"{identidade.presidente_endereco_bairro}, CEP: {identidade.presidente_endereco_cep}, "
        f"{identidade.presidente_endereco_cidade}/{identidade.presidente_endereco_estado}"
    )


def identidade_de_configuracao(identidade: IdentidadeInstitucionalModel) -> dict:
    return {
        "presidente": {
            "nome": identidade.presidente_nome,
            "cpf": identidade.presidente_cpf,
            "rg": identidade.presidente_rg,
            "orgao_emissor": identidade.presidente_orgao_emissor,
            "endereco": endereco_presidente_completo(identidade),
            "estado_civil": identidade.presidente_estado_civil,
            "nacionalidade": identidade.presidente_nacionalidade,
            "profissao": identidade.presidente_profissao,
            # Contato de apoio (não aparece no documento gerado, e não é
            # usado em nenhum fluxo automático hoje).
            "email": identidade.presidente_email,
            "telefone": identidade.presidente_telefone,
        },
        # testemunha = testemunha 1, impressa como testemunha da Insper Jr no
        # Contrato e no TEP. testemunha_alternativa = testemunha 2, padrão do
        # CONTRATANTE quando o cliente não informa testemunha própria. Ver
        # `documentos_contratuais/render_template.py`.
        "testemunha": {
            "nome": identidade.testemunha1_nome,
            "cpf": identidade.testemunha1_cpf,
            "email": identidade.testemunha1_email,
            "telefone": identidade.testemunha1_telefone,
        },
        "testemunha_alternativa": {
            "nome": identidade.testemunha2_nome,
            "cpf": identidade.testemunha2_cpf,
            "email": identidade.testemunha2_email,
            "telefone": identidade.testemunha2_telefone,
        },
    }
