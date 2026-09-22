"""Renderização dos documentos jurídicos a partir de templates .docx (docxtpl).

⭐ 2026-09-16 — porta de `contratos-backend/src/documentos/render_template.py`.
O texto e a formatação vivem nos templates em `templates/` (modelos oficiais
da Insper Jr); aqui só se monta o contexto Jinja2 a partir de `dados` +
`identidade` e se preenche o template.

Regras de testemunha (decisão do time, mantidas da Contratos):
- Lado Insper Jr (esquerda): testemunha 1 da Identidade Institucional sempre;
  a testemunha 2 entra como 2ª testemunha da Insper quando o cliente informa
  duas testemunhas próprias.
- Lado CONTRATANTE (direita): as testemunhas que o cliente informar; se ele
  não informar nenhuma, entra o padrão (testemunha 2 da Identidade
  Institucional).
- Os dois lados ficam sempre com o mesmo número de testemunhas (1-1 ou 2-2) e
  são impressos em todos os tipos de documento.
- Testemunhas são apenas nomes impressos no documento.
"""

from __future__ import annotations

import os

from docxtpl import DocxTemplate

from src.documentos_contratuais import common as C
from src.documentos_contratuais.extrair_coleta import formatar_rg, separar_rg

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

TEMPLATE_POR_TIPO = {
    "contrato": "contrato.docx",
    "tep": "tep.docx",
    "nda": "nda.docx",
    "uso_imagem": "uso_imagem.docx",
    "aditivo": "aditivo.docx",
}

_ROMANOS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def _romano(i: int) -> str:
    return _ROMANOS[i] if i < len(_ROMANOS) else str(i + 1)


# ---------- Testemunhas ----------


def _norm_testemunha(t: dict | None) -> dict | None:
    """Reduz uma testemunha ao que é impresso (nome + CPF); None se sem nome."""
    if not t or not t.get("nome"):
        return None
    return {"nome": t.get("nome", ""), "cpf": t.get("cpf", "")}


def _testemunhas_contexto(dados: dict, identidade: dict) -> dict:
    """Monta os dois lados do bloco de testemunhas, balanceados.

    - Lado Insper Jr (jr): testemunha 1 (Identidade Institucional) sempre;
      testemunha 2 entra como 2ª testemunha da Insper só quando o cliente
      informa duas testemunhas próprias.
    - Lado CONTRATANTE (ct): as testemunhas que o cliente informar; se não
      informar nenhuma, entra o padrão (testemunha 2).

    Os dois lados ficam sempre com o mesmo número de testemunhas (1-1 ou 2-2).
    """
    informadas = [t for t in (dados.get("testemunhas") or []) if t.get("nome")]
    jr = _norm_testemunha(identidade.get("testemunha"))
    alt = _norm_testemunha(identidade.get("testemunha_alternativa"))

    if len(informadas) >= 2:
        ct_testemunha = _norm_testemunha(informadas[0])
        ct_testemunha2 = _norm_testemunha(informadas[1])
        jr_testemunha2 = alt
        tem_segunda = True
    elif len(informadas) == 1:
        ct_testemunha = _norm_testemunha(informadas[0])
        ct_testemunha2 = None
        jr_testemunha2 = None
        tem_segunda = False
    else:  # cliente não informou nenhuma
        ct_testemunha = alt
        ct_testemunha2 = None
        jr_testemunha2 = None
        tem_segunda = False

    return {
        "jr_testemunha": jr,
        "jr_testemunha2": jr_testemunha2,
        "ct_testemunha": ct_testemunha,
        "ct_testemunha2": ct_testemunha2,
        "tem_segunda_testemunha": tem_segunda,
        "n_testemunhas": 4 if tem_segunda else 2,
        "n_testemunhas_ext": "quatro" if tem_segunda else "duas",
    }


# ---------- Blocos de contexto ----------


#: Nacionalidade/estado civil/profissão são substantivo e adjetivo comuns
#: dentro de uma frase corrida do contrato, não nome próprio — sempre em
#: minúsculo no documento final, não importa como a pessoa digitou no
#: formulário ("Solteiro", "CASADO", "Empresário"...).
CAMPOS_QUALIFICACAO = ("nacionalidade", "estado_civil", "profissao")

#: ⚠ `cargo`, diferente dos três acima, NÃO entra nessa régua: nos cinco
#: templates ele é impresso como título no bloco de assinatura, pareado com
#: "DIRETOR PRESIDENTE" (texto fixo, em caixa alta) do lado da Insper Jr —
#: por isso mínimo com inicial maiúscula, nunca em minúsculo.


def _normalizar_qualificacao(pessoa: dict) -> dict:
    normalizado = dict(pessoa)
    for campo in CAMPOS_QUALIFICACAO:
        valor = normalizado.get(campo)
        if isinstance(valor, str):
            normalizado[campo] = valor.strip().lower()
    cargo = normalizado.get("cargo")
    if isinstance(cargo, str) and cargo.strip():
        cargo = cargo.strip()
        normalizado["cargo"] = cargo[0].upper() + cargo[1:]
    return normalizado


def _contexto_base(tipo: str, dados: dict, identidade: dict) -> dict:
    contratante = dados.get("contratante") or {}
    rep = _normalizar_qualificacao(contratante.get("representante") or {})
    # ⭐ 2026-09-22 — a pedido: o formulário voltou a pedir RG e órgão emissor
    # num campo só ("2.027.163 SSP/SC", como a Coleta de Dados também pede e
    # como a pessoa escreve naturalmente) — os templates continuam com os
    # dois merge fields separados (`rep.rg_numero`/`rep.rg_orgao_emissor`,
    # pro texto "RG nº. X, órgão emissor Y"), então a separação acontece
    # aqui, na hora de gerar. `formatar_rg` primeiro agrupa o número (mesmo
    # pra quem digitou sem pontuação nenhuma), `separar_rg` só então quebra
    # o resultado já bonito em duas partes.
    rep["rg_numero"], rep["rg_orgao_emissor"] = separar_rg(formatar_rg(rep.get("rg") or ""))
    assinatura = dados.get("assinatura") or {}
    presidente = _normalizar_qualificacao(identidade.get("presidente") or {})

    data_assinatura = ""
    if assinatura.get("dia") and assinatura.get("mes") and assinatura.get("ano"):
        data_assinatura = C.data_extenso(
            assinatura["dia"], assinatura["mes"], assinatura["ano"]
        )

    return {
        "contratante": contratante,
        "rep": rep,
        "presidente": presidente,
        "projeto": dados.get("projeto") or {},
        "data_assinatura": data_assinatura,
        **_testemunhas_contexto(dados, identidade),
    }


def _contexto_contrato(dados: dict) -> dict:
    projeto = dados.get("projeto") or {}
    financeiro = dados.get("financeiro") or {}

    escopos = projeto.get("escopos") or []
    ambientacao = escopos[0] if escopos else {"nome": "Ambientação", "prazo_dias_uteis": 0}
    outros = escopos[1:]
    prazo_desenvolvimento = sum(e.get("prazo_dias_uteis", 0) for e in outros)
    prazo_global = sum(e.get("prazo_dias_uteis", 0) for e in escopos)
    amb_dias = ambientacao.get("prazo_dias_uteis", 0)

    num_consultores = projeto.get("num_consultores", 0)
    num_coordenadores = projeto.get("num_coordenadores", 0)

    valor_total = financeiro.get("valor_total", 0)
    parcelado = bool(financeiro.get("parcelado"))
    numero_parcelas = financeiro.get("numero_parcelas", 0)
    if parcelado:
        parcelamento_texto = (
            f"em até {numero_parcelas} ({C.numero_extenso(numero_parcelas)}) parcelas."
        )
    else:
        parcelamento_texto = "em parcela única."

    parcelas = []
    for p in C.gerar_parcelas(financeiro):
        parcelas.append(
            {
                "numero": str(p["numero"]),
                "valor": f"{C.formatar_moeda(p['valor'])} ({C.valor_extenso(p['valor'])})",
                "vencimento": f"{C.formatar_data_br(p['vencimento'])} ({C.iso_para_extenso(p['vencimento'])})",
            }
        )

    dias_excecao = projeto.get("dias_excecao") or []
    if dias_excecao:
        dias_excecao_texto = ", ".join(
            f"entre os dias {d['inicio']} e {d['fim']}" for d in dias_excecao
        )
        dias_excecao_texto = dias_excecao_texto[0].upper() + dias_excecao_texto[1:]
    else:
        dias_excecao_texto = "Não há dias de exceção definidos para este contrato"

    return {
        "servico": projeto.get("servico", ""),
        "escopos": [{"numero": _romano(i), "nome": e.get("nome", "")} for i, e in enumerate(escopos)],
        "num_consultores": num_consultores,
        "num_consultores_ext": C.numero_extenso(num_consultores),
        "num_coordenadores": num_coordenadores,
        "num_coordenadores_ext": C.numero_extenso(num_coordenadores),
        "valor_total": C.formatar_moeda(valor_total),
        "valor_total_ext": C.valor_extenso(valor_total),
        "parcelamento_texto": parcelamento_texto,
        "parcelas": parcelas,
        "tem_parcelas": bool(parcelas),
        "ambientacao_dias": amb_dias,
        "ambientacao_dias_ext": C.numero_extenso(amb_dias),
        "prazo_global": prazo_global,
        "prazo_global_ext": C.numero_extenso(prazo_global),
        "prazo_desenvolvimento": prazo_desenvolvimento,
        "prazo_desenvolvimento_ext": C.numero_extenso(prazo_desenvolvimento),
        "dias_excecao_texto": dias_excecao_texto,
    }


def _contexto_tep(dados: dict) -> dict:
    projeto = dados.get("projeto") or {}
    execucao = dados.get("execucao") or {}
    escopos = projeto.get("escopos_entregues") or []
    return {
        "projeto_nome": projeto.get("nome", ""),
        "escopos": [{"numero": _romano(i), "nome": nome} for i, nome in enumerate(escopos)],
        "execucao_inicio": C.formatar_data_br(execucao["data_inicio"]) if execucao.get("data_inicio") else "",
        "execucao_fim": C.formatar_data_br(execucao["data_fim"]) if execucao.get("data_fim") else "",
    }


def _contexto_uso_imagem(dados: dict) -> dict:
    return {"contexto": dados.get("contexto", "")}


def _contexto_aditivo(dados: dict) -> dict:
    from itertools import count as _count
    from string import ascii_lowercase

    secoes = dados.get("secoes") or {}
    contrato_principal = dados.get("contrato_principal") or {}
    objeto = dados.get("objeto") or {}
    alteracao = dados.get("alteracao") or {}
    preco = dados.get("preco") or {}
    prazo = dados.get("prazo") or {}

    contador = _count(1)

    def n() -> str:
        return f"Cláusula {next(contador)}ª"

    ctx = {"secoes": {k: bool(secoes.get(k)) for k in ("objeto", "alteracao", "preco", "prazo")}}

    ctx["n_representacao"] = n()
    ctx["contrato_ref"] = contrato_principal.get("referencia", "")
    ctx["contrato_data"] = (
        C.formatar_data_br(contrato_principal["data"]) if contrato_principal.get("data") else ""
    )
    ctx["n_contrato_principal"] = n()

    if secoes.get("objeto"):
        ctx["n_objeto"] = n()
        ctx["objeto_descricao"] = objeto.get("descricao", "")
        ctx["objeto_itens"] = [
            {"letra": ascii_lowercase[i], "texto": item}
            for i, item in enumerate(objeto.get("itens", []))
        ]

    if secoes.get("alteracao"):
        ctx["n_alteracao"] = n()
        ctx["alteracao_clausula"] = alteracao.get("clausula", "")
        ctx["alteracao_nova_redacao"] = alteracao.get("nova_redacao", "")

    if secoes.get("preco"):
        ctx["n_preco"] = n()
        parcelado = bool(preco.get("parcelado"))
        ctx["preco_parcelado"] = parcelado
        ctx["preco_antigo"] = C.formatar_moeda(preco.get("valor_antigo", 0))
        ctx["preco_antigo_ext"] = C.valor_extenso(preco.get("valor_antigo", 0))
        ctx["preco_novo"] = C.formatar_moeda(preco.get("valor_novo", 0))
        ctx["preco_novo_ext"] = C.valor_extenso(preco.get("valor_novo", 0))
        ctx["preco_sufixo"] = (
            ", a ser pago de forma parcelada conforme o cronograma abaixo, substituindo "
            "integralmente as condições de pagamento anteriormente previstas no Contrato Principal:"
            if parcelado
            else ", substituindo integralmente as condições de pagamento anteriormente previstas "
            "no Contrato Principal."
        )
        ctx["parcelas"] = [
            {
                "numero": str(p["numero"]),
                "valor": f"{C.formatar_moeda(p['valor'])} ({C.valor_extenso(p['valor'])})",
                "vencimento": f"{C.formatar_data_br(p['vencimento'])} ({C.iso_para_extenso(p['vencimento'])})",
            }
            for p in C.gerar_parcelas(preco)
        ]

    if secoes.get("prazo"):
        ctx["n_prazo"] = n()
        dias = prazo.get("dias_uteis", 0)
        ctx["prazo_dias"] = dias
        ctx["prazo_dias_ext"] = C.numero_extenso(dias)

    ctx["n_ratificacao1"] = n()
    ctx["n_ratificacao2"] = n()
    ctx["n_disp1"] = n()
    ctx["n_disp2"] = n()
    ctx["n_disp3"] = n()
    ctx["n_foro"] = n()
    return ctx


CONTEXTOS_ESPECIFICOS = {
    "contrato": _contexto_contrato,
    "tep": _contexto_tep,
    "uso_imagem": _contexto_uso_imagem,
    "aditivo": _contexto_aditivo,
    # nda: só usa o contexto base.
}


def montar_contexto(tipo: str, dados: dict, identidade: dict) -> dict:
    ctx = _contexto_base(tipo, dados, identidade)
    especifico = CONTEXTOS_ESPECIFICOS.get(tipo)
    if especifico:
        ctx.update(especifico(dados))
    return ctx


def renderizar(tipo: str, dados: dict, identidade: dict) -> DocxTemplate:
    caminho = TEMPLATE_POR_TIPO.get(tipo)
    if not caminho:
        raise ValueError(f'Não há template para documentos do tipo "{tipo}".')
    template_path = os.path.join(TEMPLATES_DIR, caminho)
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template não encontrado: {template_path}")

    doc = DocxTemplate(template_path)
    doc.render(montar_contexto(tipo, dados, identidade))
    return doc
