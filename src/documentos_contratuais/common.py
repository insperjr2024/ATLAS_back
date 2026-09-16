"""Helpers de formatação compartilhados por `render_template.py` (§ Contratos).

⭐ 2026-09-16 — porta de `contratos-backend/src/documentos/common.py`, sem
mudança de lógica: moeda, extenso, datas e parcelas de um documento jurídico
não têm nada a ver com ATLAS ou Contratos, é regra de português/contábil
pura.
"""

from __future__ import annotations

import calendar
from datetime import date

from num2words import num2words

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def texto_contratada(presidente: dict) -> str:
    """Parágrafo de qualificação da CONTRATADA (Insper Jr), verbatim nos cinco
    modelos — só o presidente muda de uma gestão para outra. `presidente` vem
    de `identidade_de_configuracao()["presidente"]`."""
    return (
        "CONTRATADA: Insper Jr, doravante denominado CONTRATADA, associação sem fins lucrativos, "
        "inscrita no CNPJ n° 04.434.382/0001-12, com sede em Rua Quatá nº 200, primeiro andar, CEP "
        "04546-042, Vila Olímpia, no município de São Paulo, estado de São Paulo, neste ato representada "
        f"na forma de seu Estatuto Social pelo seu Diretor Presidente {presidente['nome']}, "
        f"{presidente['nacionalidade']}, maior de idade, {presidente['estado_civil']}, "
        f"{presidente['profissao']}, inscrito no CPF sob o nº {presidente['cpf']}, com "
        f"cédula de identidade nº {presidente['rg']}, órgão emissor {presidente['orgao_emissor']}, "
        f"situado na {presidente['endereco']}."
    )


def formatar_moeda(valor: float) -> str:
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def valor_extenso(valor: float) -> str:
    return num2words(round(valor, 2), lang="pt_BR", to="currency")


def numero_extenso(n: int) -> str:
    return num2words(n, lang="pt_BR")


def data_extenso(dia, mes, ano) -> str:
    nome_mes = MESES[mes - 1] if isinstance(mes, int) else mes
    return f"{dia} de {nome_mes} de {ano}"


def formatar_data_br(iso: str) -> str:
    ano, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{ano}"


def iso_para_extenso(iso: str) -> str:
    ano, mes, dia = (int(p) for p in iso.split("-"))
    return data_extenso(dia, mes, ano)


def gerar_parcelas(financeiro: dict) -> list[dict]:
    if not financeiro.get("parcelado"):
        return []
    if financeiro.get("parcelas"):
        return financeiro["parcelas"]

    numero_parcelas = financeiro["numero_parcelas"]
    valor_parcela = financeiro["valor_parcela"]
    ano_ini, mes_ini, dia_ini = (int(p) for p in financeiro["primeiro_vencimento"].split("-"))
    dia_vencimento = financeiro.get("dia_vencimento_mensal", dia_ini)

    parcelas = []
    for i in range(numero_parcelas):
        mes_total = mes_ini - 1 + i
        ano = ano_ini + mes_total // 12
        mes = mes_total % 12 + 1
        ultimo_dia_do_mes = calendar.monthrange(ano, mes)[1]
        vencimento = date(ano, mes, min(dia_vencimento, ultimo_dia_do_mes))
        parcelas.append(
            {"numero": i + 1, "valor": valor_parcela, "vencimento": vencimento.isoformat()}
        )
    return parcelas
