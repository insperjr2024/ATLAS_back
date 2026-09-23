"""Campos obrigatórios de um documento jurídico (§ Contratos).

⭐ 2026-09-20 — a pedido: sem isso dava pra confirmar o preenchimento e até
gerar um contrato com CNPJ, nome do representante, tudo em branco. Mesma
régua da Coleta de Dados (`extrair_coleta.py`): "(Opcional)" é a exceção
explícita, o resto é obrigatório. Os campos realmente opcionais são e-mail/
telefone do representante e as duas testemunhas (⭐ 2026-09-22 — nem a 1ª é
mais obrigatória: quem não informar nenhuma cai no padrão institucional, ver
`_campos_testemunhas` e `render_template.py`/`_testemunhas_contexto`) — mas
quem começar a preencher uma linha de testemunha termina ela.

⭐ 2026-09-21 — cada item devolvido carrega o CAMINHO junto do rótulo (não só
o rótulo): é o que permite o front destacar o campo vazio em vez de só listar
o nome dele numa mensagem — ver `RegraDeNegocioError.campos`/`erro_de_regra`.
"""

from typing import Any, List, Tuple

from src.utils.exceptions import RegraDeNegocioError

#: (caminho, rótulo) — o mesmo par em toda a validação.
Campo = Tuple[str, str]


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


def _checar(dados: dict, campos: List[Campo]) -> List[Campo]:
    return [(caminho, rotulo) for caminho, rotulo in campos if _vazio(_obter(dados, caminho))]


CAMPOS_CONTRATANTE: List[Campo] = [
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


def _campos_testemunhas(dados: dict) -> List[Campo]:
    """⭐ 2026-09-22 — a pedido: testemunha não é obrigatória, nem a 1ª. Quem
    não informar nenhuma cai no padrão institucional (as duas testemunhas da
    Identidade Institucional — ver o balanceamento em `render_template.py`,
    `_testemunhas_contexto`). Mas quem começar a preencher uma linha termina
    ela: não dá pra imprimir nome sem CPF, nem CPF sem nome."""
    testemunhas = dados.get("testemunhas") or []
    faltando: List[Campo] = []
    for i, testemunha in enumerate(testemunhas[:2]):
        testemunha = testemunha or {}
        if _vazio(testemunha.get("nome")) and _vazio(testemunha.get("cpf")):
            continue
        if _vazio(testemunha.get("nome")):
            faltando.append((f"testemunhas.{i}.nome", f"Nome da testemunha {i + 1}"))
        if _vazio(testemunha.get("cpf")):
            faltando.append((f"testemunhas.{i}.cpf", f"CPF da testemunha {i + 1}"))
    return faltando


CAMPOS_ASSINATURA: List[Campo] = [
    ("assinatura.dia", "Dia da assinatura"),
    ("assinatura.mes", "Mês da assinatura"),
    ("assinatura.ano", "Ano da assinatura"),
]


def _campos_contrato(dados: dict) -> List[Campo]:
    faltando = _checar(
        dados,
        [
            ("projeto.servico", "Serviço a ser prestado"),
            ("financeiro.valor_total", "Valor do projeto"),
            ("financeiro.forma_pagamento", "Forma de pagamento"),
        ],
    )
    if _vazio((dados.get("projeto") or {}).get("escopos")):
        faltando.append(("projeto.escopos", "Escopos do projeto"))
    if _vazio((dados.get("projeto") or {}).get("num_consultores")):
        faltando.append(("projeto.num_consultores", "Número de consultores"))
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


def _campos_tep(dados: dict) -> List[Campo]:
    faltando = _checar(
        dados,
        [
            ("projeto.nome", "Nome do projeto"),
            ("execucao.data_inicio", "Data de início da execução"),
            ("execucao.data_fim", "Data de término da execução"),
        ],
    )
    if _vazio((dados.get("projeto") or {}).get("escopos_entregues")):
        faltando.append(("projeto.escopos_entregues", "Escopos entregues"))
    return faltando


def _campos_uso_imagem(dados: dict) -> List[Campo]:
    return _checar(dados, [("contexto", "Contexto de captação da imagem")])


def _campos_aditivo(dados: dict) -> List[Campo]:
    secoes = dados.get("secoes") or {}
    if not any(secoes.values()):
        return [("secoes", "Pelo menos uma seção do aditivo (objeto, alteração, preço ou prazo)")]

    faltando: List[Campo] = []
    if secoes.get("objeto"):
        faltando += _checar(dados, [("objeto.descricao", "Descrição do objeto do aditivo")])
        if _vazio((dados.get("objeto") or {}).get("itens")):
            faltando.append(("objeto.itens", "Itens do objeto do aditivo"))
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


def campos_faltando(tipo: str, dados: dict) -> List[Campo]:
    """Todo campo obrigatório ainda vazio: (caminho, rótulo em português).
    Lista vazia = documento completo."""
    if tipo == "outro":
        return []
    dados = dados or {}
    faltando = _checar(dados, CAMPOS_CONTRATANTE)
    faltando += _campos_testemunhas(dados)
    faltando += _checar(dados, CAMPOS_ASSINATURA)
    especifico = CAMPOS_ESPECIFICOS_POR_TIPO.get(tipo)
    if especifico:
        faltando += especifico(dados)
    return faltando


def erro_campos_faltando(faltando: List[Campo]) -> RegraDeNegocioError:
    """Uma `RegraDeNegocioError` pronta a partir do que `campos_faltando`
    devolveu — mensagem em português pra quem só mostra o texto, `campos`
    (os caminhos) pra quem destaca cada campo vazio no formulário."""
    rotulos = [rotulo for _, rotulo in faltando]
    caminhos = [caminho for caminho, _ in faltando]
    return RegraDeNegocioError(
        f"Faltam campos obrigatórios: {', '.join(rotulos)}.", campos=caminhos
    )
