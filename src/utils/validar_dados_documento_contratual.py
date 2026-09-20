"""Campos obrigatórios de um documento jurídico (§ Contratos).

⭐ 2026-09-20 — a pedido: sem isso dava pra confirmar o preenchimento e até
gerar um contrato com CNPJ, nome do representante, tudo em branco. Mesma
régua da Coleta de Dados (`extrair_coleta.py`): "(Opcional)" é a exceção
explícita, o resto é obrigatório. Os únicos campos realmente opcionais aqui
são e-mail/telefone do representante e a 2ª testemunha — nem todo cliente
traz uma segunda pessoa.
"""

from typing import Any, List, Tuple


def _obter(dados: Any, caminho: str) -> Any:
    atual = dados
    for parte in caminho.split("."):
        if isinstance(atual, list):
            try:
                atual = atual[int(parte)]
            except (ValueError, IndexError):
                return None
        elif isinstance(atual, dict):
            atual = atual.get(parte)
        else:
            return None
    return atual


def _vazio(valor: Any) -> bool:
    if valor is None:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    if isinstance(valor, (int, float)):
        return valor == 0
    if isinstance(valor, list):
        return len(valor) == 0
    return False


def _checar(dados: dict, campos: List[Tuple[str, str]]) -> List[str]:
    return [rotulo for caminho, rotulo in campos if _vazio(_obter(dados, caminho))]


CAMPOS_CONTRATANTE = [
    ("contratante.razao_social", "Razão social do contratante"),
    ("contratante.cnpj", "CNPJ do contratante"),
    ("contratante.endereco", "Endereço do contratante"),
    ("contratante.representante.nome", "Nome do representante"),
    ("contratante.representante.nacionalidade", "Nacionalidade do representante"),
    ("contratante.representante.estado_civil", "Estado civil do representante"),
    ("contratante.representante.profissao", "Profissão do representante"),
    ("contratante.representante.cargo", "Cargo do representante"),
    ("contratante.representante.rg", "RG do representante"),
    ("contratante.representante.cpf", "CPF do representante"),
    ("contratante.representante.endereco", "Endereço do representante"),
]

#: Só a testemunha 1 é obrigatória — a 2ª é opcional pros dois lados (ver a
#: regra de balanceamento em `render_template.py`).
CAMPOS_TESTEMUNHA_1 = [
    ("testemunhas.0.nome", "Nome da testemunha 1"),
    ("testemunhas.0.cpf", "CPF da testemunha 1"),
]

CAMPOS_ASSINATURA = [
    ("assinatura.dia", "Dia da assinatura"),
    ("assinatura.mes", "Mês da assinatura"),
    ("assinatura.ano", "Ano da assinatura"),
]


def _campos_contrato(dados: dict) -> List[str]:
    faltando = _checar(
        dados,
        [
            ("projeto.servico", "Serviço a ser prestado"),
            ("financeiro.valor_total", "Valor do projeto"),
            ("financeiro.forma_pagamento", "Forma de pagamento"),
        ],
    )
    if _vazio((dados.get("projeto") or {}).get("escopos")):
        faltando.append("Escopos do projeto")
    if _vazio((dados.get("projeto") or {}).get("num_consultores")):
        faltando.append("Número de consultores")
    if (dados.get("financeiro") or {}).get("parcelado"):
        faltando += _checar(
            dados,
            [
                ("financeiro.numero_parcelas", "Número de parcelas"),
                ("financeiro.primeiro_vencimento", "Data do primeiro vencimento"),
                ("financeiro.dia_vencimento_mensal", "Dia do vencimento mensal"),
            ],
        )
    return faltando


def _campos_tep(dados: dict) -> List[str]:
    faltando = _checar(
        dados,
        [
            ("projeto.nome", "Nome do projeto"),
            ("execucao.data_inicio", "Data de início da execução"),
            ("execucao.data_fim", "Data de término da execução"),
        ],
    )
    if _vazio((dados.get("projeto") or {}).get("escopos_entregues")):
        faltando.append("Escopos entregues")
    return faltando


def _campos_uso_imagem(dados: dict) -> List[str]:
    return _checar(dados, [("contexto", "Contexto de captação da imagem")])


def _campos_aditivo(dados: dict) -> List[str]:
    secoes = dados.get("secoes") or {}
    if not any(secoes.values()):
        return ["Pelo menos uma seção do aditivo (objeto, alteração, preço ou prazo)"]

    faltando: List[str] = []
    if secoes.get("objeto"):
        faltando += _checar(dados, [("objeto.descricao", "Descrição do objeto do aditivo")])
        if _vazio((dados.get("objeto") or {}).get("itens")):
            faltando.append("Itens do objeto do aditivo")
    if secoes.get("alteracao"):
        faltando += _checar(
            dados,
            [
                ("alteracao.clausula", "Cláusula alterada"),
                ("alteracao.nova_redacao", "Nova redação da cláusula"),
            ],
        )
    if secoes.get("preco"):
        faltando += _checar(dados, [("preco.valor_novo", "Novo valor do contrato")])
        if (dados.get("preco") or {}).get("parcelado"):
            faltando += _checar(
                dados,
                [
                    ("preco.numero_parcelas", "Número de parcelas do aditivo"),
                    ("preco.primeiro_vencimento", "Data do primeiro vencimento do aditivo"),
                    ("preco.dia_vencimento_mensal", "Dia do vencimento mensal do aditivo"),
                ],
            )
    if secoes.get("prazo"):
        faltando += _checar(dados, [("prazo.dias_uteis", "Novo prazo em dias úteis")])
    return faltando


#: "nda" não entra aqui — só os campos comuns (contratante/testemunha/
#: assinatura) já cobrem o documento inteiro. "outro" (Importar Antigo)
#: nunca passa por aqui — nasce sem formulário e sem esses três blocos.
CAMPOS_ESPECIFICOS_POR_TIPO = {
    "contrato": _campos_contrato,
    "tep": _campos_tep,
    "uso_imagem": _campos_uso_imagem,
    "aditivo": _campos_aditivo,
}


def campos_faltando(tipo: str, dados: dict) -> List[str]:
    """Todo campo obrigatório ainda vazio, em português, pronto pra virar
    mensagem de erro. Lista vazia = documento completo."""
    if tipo == "outro":
        return []
    dados = dados or {}
    faltando = _checar(dados, CAMPOS_CONTRATANTE)
    faltando += _checar(dados, CAMPOS_TESTEMUNHA_1)
    faltando += _checar(dados, CAMPOS_ASSINATURA)
    especifico = CAMPOS_ESPECIFICOS_POR_TIPO.get(tipo)
    if especifico:
        faltando += especifico(dados)
    return faltando
