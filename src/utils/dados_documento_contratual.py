"""Como cada tipo de documento jurídico nasce preenchido (§ Contratos).

⭐ 2026-09-16 — porta de `contratos-backend/src/use_cases/projeto/avancar_status.py`
(as funções `_dados_iniciais_*`/`DADOS_INICIAIS_POR_TIPO`), sem a parte que
lê a "Coleta de Dados" (upload de .docx com extração automática) — recurso
que ainda não existe no ATLAS; enquanto isso, um projeto sem Contrato de
Prestação na plataforma simplesmente não tem de onde herdar, e os campos
nascem em branco.

Um documento ADICIONAL (TEP, NDA, Uso de Imagem, Aditivo) herda do Contrato
de Prestação do MESMO projeto, quando ele existe — contratante e testemunhas
não deveriam ter de ser digitados duas vezes.
"""

from typing import Callable, Optional

from src.documentos_contratuais.common import MESES


def _contratante_em_branco() -> dict:
    representante = {
        "nome": "", "nacionalidade": "", "estado_civil": "", "profissao": "",
        "cargo": "", "rg": "", "cpf": "", "endereco": "", "email": "", "telefone": "",
    }
    return {
        "razao_social": "",
        "cnpj": "",
        "endereco": "",
        "representante": representante,
        "email_cobranca": "",
    }


def _testemunhas_em_branco() -> list:
    # 2 posições em branco: o formulário só edita posições já existentes no
    # array, não tem botão de adicionar.
    return [{"nome": "", "cpf": ""}, {"nome": "", "cpf": ""}]


def dados_iniciais_contrato() -> dict:
    """Contrato de Prestação de Serviços em branco — nasce assim quando
    aberto num projeto que ainda não tem um."""
    return {
        "projeto": {
            "servico": "",
            "escopos": [],
            "num_consultores": 0,
            "num_coordenadores": 0,
            "dias_excecao": [],
            "data_inicio": "",
            "data_termino": "",
        },
        "contratante": _contratante_em_branco(),
        "financeiro": {
            "valor_total": 0,
            "parcelado": False,
            "numero_parcelas": 0,
            "valor_parcela": 0,
            "primeiro_vencimento": "",
            "dia_vencimento_mensal": 0,
            "forma_pagamento": "",
        },
        "testemunhas": _testemunhas_em_branco(),
        "assinatura": {"dia": "", "mes": "", "ano": None},
    }


def dados_iniciais_tep(dados_contrato: dict, nome_projeto: str) -> dict:
    return {
        "projeto": {
            "nome": nome_projeto,
            "escopos_entregues": [e["nome"] for e in dados_contrato.get("projeto", {}).get("escopos", [])],
        },
        "contratante": dados_contrato.get("contratante") or _contratante_em_branco(),
        "execucao": {"data_inicio": "", "data_fim": ""},
        "testemunhas": dados_contrato.get("testemunhas") or _testemunhas_em_branco(),
        "assinatura": {"dia": "", "mes": "", "ano": None},
    }


def dados_iniciais_nda(dados_contrato: dict, nome_projeto: str) -> dict:
    # O NDA é inteiramente herdado (quando há um Contrato de PS pra herdar):
    # só falta a data de assinatura.
    return {
        "contratante": dados_contrato.get("contratante") or _contratante_em_branco(),
        "testemunhas": dados_contrato.get("testemunhas") or _testemunhas_em_branco(),
        "assinatura": {"dia": "", "mes": "", "ano": None},
    }


def dados_iniciais_uso_imagem(dados_contrato: dict, nome_projeto: str) -> dict:
    return {
        "contratante": dados_contrato.get("contratante") or _contratante_em_branco(),
        # Preenche a Cláusula 2ª ("captados no contexto de ..."). Começa com
        # o nome do projeto como chute razoável, mas é editável.
        "contexto": nome_projeto,
        "testemunhas": dados_contrato.get("testemunhas") or _testemunhas_em_branco(),
        "assinatura": {"dia": "", "mes": "", "ano": None},
    }


def _assinatura_para_iso(assinatura: dict) -> str:
    """Converte {dia, mes (texto livre), ano} — como o time digitou na
    assinatura do Contrato de Prestação — pra "YYYY-MM-DD". `mes` não vem de
    um select fixo, então aceita erro de parsing com string vazia em vez de
    estourar — o campo só volta a pedir preenchimento manual."""
    dia, mes, ano = assinatura.get("dia"), assinatura.get("mes"), assinatura.get("ano")
    if not dia or not mes or not ano:
        return ""
    try:
        mes_num = int(mes)
    except (TypeError, ValueError):
        try:
            mes_num = [m.lower() for m in MESES].index(str(mes).strip().lower()) + 1
        except ValueError:
            return ""
    try:
        return f"{int(ano):04d}-{mes_num:02d}-{int(dia):02d}"
    except (TypeError, ValueError):
        return ""


def dados_iniciais_aditivo(dados_contrato: dict, nome_projeto: str) -> dict:
    financeiro = dados_contrato.get("financeiro") or {}
    return {
        "contratante": dados_contrato.get("contratante") or _contratante_em_branco(),
        # Só existe um "contrato principal" possível: o Contrato de Prestação
        # de Serviços do próprio projeto. A data vem da assinatura já
        # registrada nele — o sistema não numera contratos, então a
        # referência fica com um texto padrão que o time pode ajustar.
        "contrato_principal": {
            "referencia": "de Prestação de Serviços",
            "data": _assinatura_para_iso(dados_contrato.get("assinatura") or {}),
        },
        # Nenhuma seção marcada: o time escolhe o que este aditivo altera.
        "secoes": {"objeto": False, "alteracao": False, "preco": False, "prazo": False},
        "objeto": {"descricao": "", "itens": []},
        "alteracao": {"clausula": "", "nova_redacao": ""},
        "preco": {
            # O valor "de" já é conhecido: é o do contrato vigente.
            "valor_antigo": financeiro.get("valor_total"),
            "valor_novo": None,
            "parcelado": False,
            "numero_parcelas": None,
            "valor_parcela": None,
            "primeiro_vencimento": "",
            "dia_vencimento_mensal": None,
        },
        "prazo": {"dias_uteis": None},
        "testemunhas": dados_contrato.get("testemunhas") or _testemunhas_em_branco(),
        "assinatura": {"dia": "", "mes": "", "ano": None},
    }


#: Como pré-preencher cada tipo ADICIONAL a partir do Contrato de Prestação
#: do projeto, quando ele existir (ver `AbrirDocumentoContratualUseCase`). O
#: tipo raiz (`contrato`) não entra aqui — ele usa `dados_iniciais_contrato()`
#: direto, sem base nenhuma pra herdar.
DADOS_INICIAIS_POR_TIPO: dict[str, Callable[[dict, str], dict]] = {
    "tep": dados_iniciais_tep,
    "nda": dados_iniciais_nda,
    "uso_imagem": dados_iniciais_uso_imagem,
    "aditivo": dados_iniciais_aditivo,
}


def montar_dados_iniciais(tipo: str, dados_contrato_raiz: Optional[dict], nome_projeto: str) -> dict:
    """`dados_contrato_raiz` é o `dados` do Contrato de Prestação do mesmo
    projeto, quando ele existe (`None` caso contrário — o projeto ainda não
    tem um, ou nunca vai ter, ex.: institucional)."""
    if tipo == "contrato":
        return dados_iniciais_contrato()
    montar = DADOS_INICIAIS_POR_TIPO.get(tipo)
    if montar is None:
        # "outro" (Importar Antigo) não tem formulário — nasce sem `dados`.
        return {}
    return montar(dados_contrato_raiz or {}, nome_projeto)
